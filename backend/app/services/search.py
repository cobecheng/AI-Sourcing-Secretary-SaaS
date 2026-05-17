import hashlib
import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import Project, ProjectMemory
from app.schemas.search import SearchResultRecord, SearchSuppliersResponse


EXA_SEARCH_URL = "https://api.exa.ai/search"

# Search safety defaults:
# - mock mode remains default
# - real Exa search requires MOCK_MODE=false, ENABLE_REAL_SEARCH=true, and EXA_API_KEY
# - search only records public result metadata; it does not scrape pages, submit forms, or trigger outreach
SAFETY_DEFAULTS = {
    "requires_explicit_real_mode": True,
    "requires_api_key_for_real_search": True,
    "scrapes_pages": False,
    "submits_forms": False,
    "sends_outreach": False,
}


@dataclass(frozen=True)
class SearchRun:
    provider: str
    mock_mode: bool
    fallback_reason: str | None
    results: list[SearchResultRecord]


def search_suppliers(
    db: Session,
    project_id: int,
    query: str,
    limit: int | None = None,
) -> SearchSuppliersResponse:
    settings = get_settings()
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    bounded_limit = min(limit or settings.max_search_results, settings.max_search_results)
    cache_key = _cache_key(query=query, limit=bounded_limit)
    cached = _get_cached_search(db, project.id, cache_key)
    if cached is not None:
        return _response_from_cache(project.id, query, cached, settings)

    run = _run_search(settings=settings, query=query, limit=bounded_limit)
    memory = _store_search_cache(db, project.id, cache_key, query, bounded_limit, run)
    db.commit()
    return _response_from_cache(project.id, query, memory, settings, cache_status="stored")


def _run_search(settings: Settings, query: str, limit: int) -> SearchRun:
    if settings.mock_mode or not settings.enable_real_search:
        return SearchRun(
            provider="mock_search",
            mock_mode=True,
            fallback_reason="mock_mode_or_real_search_disabled",
            results=_mock_results(query, limit),
        )

    if settings.search_provider != "exa":
        raise HTTPException(status_code=400, detail="Only the exa search provider is currently supported")
    if not settings.exa_api_key:
        return SearchRun(
            provider="mock_search",
            mock_mode=True,
            fallback_reason="missing_exa_api_key",
            results=_mock_results(query, limit),
        )

    return SearchRun(
        provider="exa",
        mock_mode=False,
        fallback_reason=None,
        results=_exa_search(settings, query, limit),
    )


def _exa_search(settings: Settings, query: str, limit: int) -> list[SearchResultRecord]:
    payload = json.dumps(
        {
            "query": query,
            "numResults": limit,
            "type": "auto",
            "contents": {"text": False, "highlights": True},
        }
    ).encode("utf-8")
    request = Request(
        EXA_SEARCH_URL,
        data=payload,
        method="POST",
        headers={
            "x-api-key": settings.exa_api_key,
            "Content-Type": "application/json",
        },
    )

    try:
        with urlopen(request, timeout=settings.search_request_timeout_seconds) as response:
            payload_json = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Exa rejected search request: {exc.code}") from exc
    except (TimeoutError, URLError) as exc:
        raise HTTPException(status_code=504, detail="Exa search request timed out or could not connect") from exc
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Exa returned an invalid JSON response") from exc

    results = payload_json.get("results") or []
    return [
        SearchResultRecord(
            source_url=str(item.get("url") or ""),
            title=str(item.get("title") or item.get("url") or "Untitled result"),
            snippet=_snippet_from_exa_item(item),
            query=query,
            provider="exa",
            rank=index + 1,
        )
        for index, item in enumerate(results[:limit])
        if item.get("url")
    ]


def _mock_results(query: str, limit: int) -> list[SearchResultRecord]:
    fixtures = [
        (
            "https://example.test/cardtrade-wholesale/pokemon",
            "CardTrade Wholesale UK Pokemon sealed products",
            "Mock search result: wholesale Pokemon booster boxes and ETBs for trade accounts.",
        ),
        (
            "https://example.test/eu-tcg-distribution/contact",
            "EU TCG Distribution wholesale inquiry",
            "Mock search result: contact form for EU retailers seeking sealed TCG products.",
        ),
        (
            "https://example.test/specialist-cards-import/trade",
            "Specialist Cards Import trade account",
            "Mock search result: importer trade page with partial Pokemon allocation evidence.",
        ),
    ]
    return [
        SearchResultRecord(
            source_url=url,
            title=title,
            snippet=snippet,
            query=query,
            provider="mock_search",
            rank=index + 1,
        )
        for index, (url, title, snippet) in enumerate(fixtures[:limit])
    ]


def _snippet_from_exa_item(item: dict[str, Any]) -> str:
    highlights = item.get("highlights")
    if isinstance(highlights, list) and highlights:
        return str(highlights[0])[:500]
    text = item.get("text")
    if isinstance(text, str) and text:
        return text[:500]
    return str(item.get("summary") or item.get("url") or "")[:500]


def _cache_key(query: str, limit: int) -> str:
    normalized = f"{query.strip().lower()}:{limit}"
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"search_results:{digest}"


def _get_cached_search(db: Session, project_id: int, cache_key: str) -> ProjectMemory | None:
    return db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == cache_key))


def _store_search_cache(
    db: Session,
    project_id: int,
    cache_key: str,
    query: str,
    limit: int,
    run: SearchRun,
) -> ProjectMemory:
    value = {
        "query": query,
        "limit": limit,
        "provider": run.provider,
        "mock_mode": run.mock_mode,
        "fallback_reason": run.fallback_reason,
        "results": [result.model_dump() for result in run.results],
    }
    memory = _get_cached_search(db, project_id, cache_key)
    if memory is None:
        memory = ProjectMemory(project_id=project_id, key=cache_key, value=value)
        db.add(memory)
    else:
        memory.value = value
    db.flush()
    return memory


def _response_from_cache(
    project_id: int,
    query: str,
    memory: ProjectMemory,
    settings: Settings,
    cache_status: str = "hit",
) -> SearchSuppliersResponse:
    value = memory.value
    results = [SearchResultRecord(**item) for item in value["results"]]
    return SearchSuppliersResponse(
        project_id=project_id,
        query=query,
        provider=value["provider"],
        mock_mode=value["mock_mode"],
        cache_status=cache_status,
        fallback_reason=value.get("fallback_reason"),
        results=results,
        safety=_safety_payload(settings),
    )


def _safety_payload(settings: Settings) -> dict[str, object]:
    return {
        **SAFETY_DEFAULTS,
        "provider": settings.search_provider,
        "real_search_enabled": settings.enable_real_search and not settings.mock_mode and bool(settings.exa_api_key),
        "request_timeout_seconds": settings.search_request_timeout_seconds,
        "max_search_results": settings.max_search_results,
    }
