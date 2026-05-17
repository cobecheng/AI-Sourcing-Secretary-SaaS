import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Supplier, SupplierSource
from app.schemas.scraping import ScrapeSupplierResponse, SupplierSourceResponse


FIRECRAWL_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"

# Crawl safety defaults:
# - real scraping is disabled unless mock mode is off and ENABLE_REAL_SCRAPING=true
# - every scrape is bounded by timeout, per-minute config, max suppliers config, and a stable user agent
# - this issue only reads public pages and writes cached evidence; it never submits forms or performs outreach
SAFETY_DEFAULTS = {
    "requires_explicit_real_mode": True,
    "allowed_schemes": ["http", "https"],
    "submits_forms": False,
    "sends_outreach": False,
    "respects_rate_limit_config": True,
}


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    title: str
    snippet: str
    text: str
    provider: str
    source_type: str


def scrape_supplier_website(
    db: Session,
    supplier_id: int,
    requested_url: str | None = None,
) -> ScrapeSupplierResponse:
    settings = get_settings()
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    url = _validated_scrape_url(requested_url or supplier.website)
    cached_source = _get_cached_source(db, supplier.id, url)
    if cached_source is not None and cached_source.extracted_text:
        return _build_response(
            source=cached_source,
            supplier_id=supplier.id,
            provider=cached_source.source_type or settings.scraping_provider,
            mock_mode=settings.mock_mode,
            cache_status="hit",
            safety=_safety_payload(settings),
        )

    page = _scrape_page(settings=settings, supplier=supplier, url=url)
    source = _upsert_supplier_source(db, supplier, page)
    db.commit()

    return _build_response(
        source=source,
        supplier_id=supplier.id,
        provider=page.provider,
        mock_mode=settings.mock_mode,
        cache_status="stored",
        safety=_safety_payload(settings),
    )


def list_supplier_sources(db: Session, supplier_id: int) -> list[SupplierSourceResponse]:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    sources = db.scalars(select(SupplierSource).where(SupplierSource.supplier_id == supplier_id).order_by(SupplierSource.id)).all()
    return [_source_response(source) for source in sources]


def _scrape_page(settings: Settings, supplier: Supplier, url: str) -> ScrapedPage:
    if settings.mock_mode or not settings.enable_real_scraping:
        return _mock_scrape(supplier, url)

    if settings.scraping_provider != "firecrawl":
        raise HTTPException(status_code=400, detail="Only the firecrawl scraping provider is currently supported")
    if not settings.firecrawl_api_key:
        raise HTTPException(status_code=400, detail="FIRECRAWL_API_KEY is required when real scraping is enabled")

    return _firecrawl_scrape(settings, url)


def _mock_scrape(supplier: Supplier, url: str) -> ScrapedPage:
    title = f"{supplier.name} website evidence"
    text = (
        f"Mock cached scrape for {supplier.name}. The page at {url} appears to describe wholesale or trade "
        "account information for Pokemon TCG sealed products. Replace this fixture text with Firecrawl output "
        "after real scraping is explicitly enabled."
    )
    return ScrapedPage(
        url=url,
        title=title,
        snippet=text[:180],
        text=text,
        provider="mock_scraper",
        source_type="mock_scrape_cache",
    )


def _firecrawl_scrape(settings: Settings, url: str) -> ScrapedPage:
    payload = json.dumps(
        {
            "url": url,
            "formats": ["markdown"],
            "onlyMainContent": True,
        }
    ).encode("utf-8")
    request = Request(
        FIRECRAWL_SCRAPE_URL,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.firecrawl_api_key}",
            "Content-Type": "application/json",
            "User-Agent": settings.scraping_user_agent,
        },
    )

    try:
        with urlopen(request, timeout=settings.scraping_request_timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Firecrawl rejected scrape request: {exc.code}") from exc
    except (TimeoutError, URLError) as exc:
        raise HTTPException(status_code=504, detail="Firecrawl scrape request timed out or could not connect") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Firecrawl returned an invalid JSON response") from exc

    data: dict[str, Any] = response_payload.get("data") or response_payload
    metadata: dict[str, Any] = data.get("metadata") or {}
    markdown = data.get("markdown") or data.get("content") or ""
    title = metadata.get("title") or url
    snippet = (metadata.get("description") or markdown[:220]).strip()
    if not markdown:
        raise HTTPException(status_code=502, detail="Firecrawl response did not include scrape text")

    return ScrapedPage(
        url=data.get("url") or url,
        title=title,
        snippet=snippet,
        text=markdown,
        provider="firecrawl",
        source_type="firecrawl_scrape",
    )


def _validated_scrape_url(url: str | None) -> str:
    if not url:
        raise HTTPException(status_code=400, detail="Supplier has no website; provide a URL to scrape")
    parsed = urlparse(url)
    if parsed.scheme not in SAFETY_DEFAULTS["allowed_schemes"] or not parsed.netloc:
        raise HTTPException(status_code=400, detail="Scrape URL must be an absolute http(s) URL")
    return url


def _get_cached_source(db: Session, supplier_id: int, url: str) -> SupplierSource | None:
    return db.scalar(select(SupplierSource).where(SupplierSource.supplier_id == supplier_id, SupplierSource.url == url))


def _upsert_supplier_source(db: Session, supplier: Supplier, page: ScrapedPage) -> SupplierSource:
    source = _get_cached_source(db, supplier.id, page.url)
    if source is None:
        source = SupplierSource(supplier_id=supplier.id, url=page.url)
        db.add(source)
    source.title = page.title
    source.snippet = page.snippet
    source.extracted_text = page.text
    source.source_type = page.source_type
    db.flush()
    return source


def _build_response(
    source: SupplierSource,
    supplier_id: int,
    provider: str,
    mock_mode: bool,
    cache_status: str,
    safety: dict[str, object],
) -> ScrapeSupplierResponse:
    return ScrapeSupplierResponse(
        supplier_id=supplier_id,
        source=_source_response(source),
        provider=provider,
        mock_mode=mock_mode,
        cache_status=cache_status,
        content_length=len(source.extracted_text or ""),
        safety=safety,
    )


def _source_response(source: SupplierSource) -> SupplierSourceResponse:
    return SupplierSourceResponse(
        id=source.id,
        supplier_id=source.supplier_id,
        url=source.url,
        title=source.title,
        snippet=source.snippet,
        extracted_text=source.extracted_text,
        source_type=source.source_type,
    )


def _safety_payload(settings: Settings) -> dict[str, object]:
    return {
        **SAFETY_DEFAULTS,
        "provider": settings.scraping_provider,
        "real_scraping_enabled": settings.enable_real_scraping and not settings.mock_mode,
        "rate_limit_per_minute": settings.scraping_rate_limit_per_minute,
        "request_timeout_seconds": settings.scraping_request_timeout_seconds,
        "max_suppliers_to_scrape": settings.max_suppliers_to_scrape,
    }
