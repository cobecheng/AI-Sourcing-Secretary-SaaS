from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlparse, urlunparse

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Project, ProjectMemory, Supplier, SupplierSource
from app.schemas.llm import LLMCompleteRequest
from app.schemas.search import SearchResultRecord
from app.schemas.suppliers import (
    ExtractSuppliersResponse,
    SupplierEvidenceResponse,
    SupplierResponse,
    SupplierScoreMetadata,
)
from app.services.llm_router import route_llm_call


LOW_CONFIDENCE_THRESHOLD = 0.60
RELEVANT_TERMS = {"pokemon", "tcg", "wholesale", "distributor", "distribution", "trade", "sealed", "booster", "etb"}
TRUST_TERMS = {"wholesale", "distributor", "distribution", "trade account", "contact", "inquiry"}


class SupplierCandidate(BaseModel):
    name: str = Field(min_length=2)
    website: str = Field(min_length=8)
    normalized_domain: str = Field(min_length=3)
    supplier_type: str | None = None
    contact_method: str | None = None
    country: str | None = None
    evidence: list[SearchResultRecord] = Field(min_length=1)

    @field_validator("website")
    @classmethod
    def validate_website(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Supplier website must be an absolute HTTP URL")
        return value


@dataclass
class ScoredCandidate:
    candidate: SupplierCandidate
    relevance_score: float
    trust_score: float
    confidence: float
    routing_decision: str
    fallback_used: bool


def extract_suppliers_from_search_results(
    db: Session,
    project_id: int,
    results: list[SearchResultRecord] | None = None,
) -> ExtractSuppliersResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    records = results if results is not None else _latest_cached_search_results(db, project_id)
    try:
        candidates = _dedupe_candidates([_candidate_from_result(result) for result in records])
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid supplier candidate: {exc}") from exc
    scored = [_score_candidate(candidate) for candidate in candidates]

    created = 0
    updated = 0
    suppliers: list[Supplier] = []
    for item in scored:
        supplier, was_created = _upsert_supplier(db, project_id, item)
        created += 1 if was_created else 0
        updated += 0 if was_created else 1
        _upsert_score_memory(db, project_id, supplier, item)
        suppliers.append(supplier)

    db.commit()
    for supplier in suppliers:
        db.refresh(supplier)

    return ExtractSuppliersResponse(
        project_id=project_id,
        candidates_seen=len(records),
        suppliers_created=created,
        suppliers_updated=updated,
        duplicates_merged=max(len(records) - len(candidates), 0),
        mock_mode=get_settings().mock_mode,
        suppliers=[supplier_response(db, supplier) for supplier in suppliers],
        safety={
            "deterministic_url_normalization": True,
            "domain_deduplication": True,
            "schema_validation": True,
            "sends_outreach": False,
            "submits_forms": False,
        },
    )


def list_project_suppliers(db: Session, project_id: int) -> list[SupplierResponse]:
    suppliers = db.scalars(select(Supplier).where(Supplier.project_id == project_id).order_by(Supplier.relevance_score.desc(), Supplier.id)).all()
    return [supplier_response(db, supplier) for supplier in suppliers]


def get_supplier(db: Session, supplier_id: int) -> SupplierResponse:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier_response(db, supplier)


def supplier_response(db: Session, supplier: Supplier) -> SupplierResponse:
    sources = db.scalars(select(SupplierSource).where(SupplierSource.supplier_id == supplier.id).order_by(SupplierSource.id)).all()
    metadata = _score_memory(db, supplier.project_id, supplier.id)
    return SupplierResponse(
        id=supplier.id,
        project_id=supplier.project_id,
        name=supplier.name,
        website=supplier.website,
        country=supplier.country,
        email=supplier.email,
        supplier_type=supplier.supplier_type,
        contact_method=supplier.contact_method,
        trust_score=float(supplier.trust_score) if supplier.trust_score is not None else None,
        relevance_score=float(supplier.relevance_score) if supplier.relevance_score is not None else None,
        status=supplier.status,
        notes=supplier.notes,
        evidence=[
            SupplierEvidenceResponse(
                url=source.url,
                title=source.title,
                snippet=source.snippet,
                source_type=source.source_type,
            )
            for source in sources
        ],
        scoring_metadata=SupplierScoreMetadata(**metadata.value) if metadata else None,
    )


def normalize_supplier_url(url: str) -> str:
    candidate = url.strip()
    if not candidate:
        raise ValueError("URL is required")
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if not host or any(character.isspace() for character in host):
        raise ValueError("URL host is required")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), host, path, "", "", ""))


def normalized_domain(url: str) -> str:
    normalized = normalize_supplier_url(url)
    return urlparse(normalized).netloc


def _latest_cached_search_results(db: Session, project_id: int) -> list[SearchResultRecord]:
    memory = db.scalar(
        select(ProjectMemory)
        .where(ProjectMemory.project_id == project_id, ProjectMemory.key.like("search_results:%"))
        .order_by(ProjectMemory.updated_at.desc(), ProjectMemory.id.desc())
    )
    if memory is None:
        return []
    return [SearchResultRecord(**item) for item in memory.value.get("results", [])]


def _candidate_from_result(result: SearchResultRecord) -> SupplierCandidate:
    normalized_url = normalize_supplier_url(result.source_url)
    domain = normalized_domain(normalized_url)
    return SupplierCandidate(
        name=_supplier_name(result, domain),
        website=f"{urlparse(normalized_url).scheme}://{domain}",
        normalized_domain=domain,
        supplier_type=_supplier_type(result),
        contact_method=_contact_method(result),
        country=_country_hint(result),
        evidence=[result],
    )


def _dedupe_candidates(candidates: list[SupplierCandidate]) -> list[SupplierCandidate]:
    by_domain: dict[str, SupplierCandidate] = {}
    for candidate in candidates:
        existing = by_domain.get(candidate.normalized_domain)
        if existing is None:
            by_domain[candidate.normalized_domain] = candidate
            continue
        merged_evidence = [*existing.evidence, *candidate.evidence]
        by_domain[candidate.normalized_domain] = existing.model_copy(
            update={
                "name": existing.name if len(existing.name) >= len(candidate.name) else candidate.name,
                "contact_method": existing.contact_method or candidate.contact_method,
                "supplier_type": existing.supplier_type or candidate.supplier_type,
                "country": existing.country or candidate.country,
                "evidence": merged_evidence,
            }
        )
    return list(by_domain.values())


def _score_candidate(candidate: SupplierCandidate) -> ScoredCandidate:
    evidence_text = " ".join(
        f"{item.title} {item.snippet} {item.source_url}" for item in candidate.evidence
    ).lower()
    relevance_hits = sum(1 for term in RELEVANT_TERMS if term in evidence_text)
    trust_hits = sum(1 for term in TRUST_TERMS if term in evidence_text)
    relevance = min(0.30 + relevance_hits * 0.08, 0.96)
    trust = min(0.35 + trust_hits * 0.07 + (0.06 if candidate.website.startswith("https://") else 0), 0.94)
    confidence = round((relevance + trust) / 2, 4)
    routing = route_llm_call(
        LLMCompleteRequest(
            project_id=0,
            task_type="supplier_relevance_scoring",
            prompt="Score supplier candidate relevance and trust using provided evidence.",
            input_json={
                "name": candidate.name,
                "website": candidate.website,
                "evidence": [item.model_dump() for item in candidate.evidence],
            },
            confidence=confidence,
            required_output_fields=["name", "website", "evidence"],
        )
    )
    return ScoredCandidate(
        candidate=candidate,
        relevance_score=round(relevance, 4),
        trust_score=round(trust, 4),
        confidence=confidence,
        routing_decision=routing.decision,
        fallback_used=routing.fallback_used,
    )


def _upsert_supplier(db: Session, project_id: int, item: ScoredCandidate) -> tuple[Supplier, bool]:
    supplier = db.scalar(
        select(Supplier).where(Supplier.project_id == project_id, Supplier.website == item.candidate.website)
    )
    created = supplier is None
    if supplier is None:
        supplier = Supplier(project_id=project_id, name=item.candidate.name, website=item.candidate.website)
        db.add(supplier)
    supplier.name = item.candidate.name
    supplier.country = item.candidate.country
    supplier.supplier_type = item.candidate.supplier_type
    supplier.contact_method = item.candidate.contact_method
    supplier.relevance_score = Decimal(str(item.relevance_score))
    supplier.trust_score = Decimal(str(item.trust_score))
    supplier.status = "Manual Review Needed" if item.confidence < LOW_CONFIDENCE_THRESHOLD else "Verified"
    supplier.notes = (
        f"Extraction confidence {item.confidence:.2f}; routing={item.routing_decision}; "
        f"evidence_count={len(item.candidate.evidence)}."
    )
    db.flush()
    for evidence in item.candidate.evidence:
        _upsert_source(db, supplier, evidence)
    db.flush()
    return supplier, created


def _upsert_source(db: Session, supplier: Supplier, evidence: SearchResultRecord) -> SupplierSource:
    normalized_url = normalize_supplier_url(evidence.source_url)
    source = db.scalar(select(SupplierSource).where(SupplierSource.supplier_id == supplier.id, SupplierSource.url == normalized_url))
    if source is None:
        source = SupplierSource(supplier_id=supplier.id, url=normalized_url)
        db.add(source)
    source.title = evidence.title
    source.snippet = evidence.snippet
    source.source_type = evidence.provider
    db.flush()
    return source


def _upsert_score_memory(db: Session, project_id: int, supplier: Supplier, item: ScoredCandidate) -> ProjectMemory:
    key = f"supplier_score:{supplier.id}"
    value = {
        "confidence": item.confidence,
        "relevance_score": item.relevance_score,
        "trust_score": item.trust_score,
        "routing_decision": item.routing_decision,
        "fallback_used": item.fallback_used,
        "evidence_urls": [normalize_supplier_url(evidence.source_url) for evidence in item.candidate.evidence],
        "normalized_domain": item.candidate.normalized_domain,
    }
    memory = _score_memory(db, project_id, supplier.id)
    if memory is None:
        memory = ProjectMemory(project_id=project_id, key=key, value=value)
        db.add(memory)
    else:
        memory.value = value
    db.flush()
    return memory


def _score_memory(db: Session, project_id: int, supplier_id: int) -> ProjectMemory | None:
    return db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == f"supplier_score:{supplier_id}"))


def _supplier_name(result: SearchResultRecord, domain: str) -> str:
    title = result.title.strip()
    if title:
        for separator in (" - ", " | ", ":", " wholesale", " Wholesale"):
            if separator in title:
                title = title.split(separator)[0]
                break
        return title[:120]
    return domain.split(".")[0].replace("-", " ").title()


def _supplier_type(result: SearchResultRecord) -> str | None:
    text = f"{result.title} {result.snippet}".lower()
    if "import" in text:
        return "Importer"
    if "distributor" in text or "distribution" in text:
        return "Distributor"
    if "wholesale" in text:
        return "Wholesaler"
    return None


def _contact_method(result: SearchResultRecord) -> str | None:
    text = f"{result.source_url} {result.title} {result.snippet}".lower()
    if "contact" in text or "inquiry" in text or "form" in text:
        return "contact_form"
    if "email" in text:
        return "email"
    return "manual_review"


def _country_hint(result: SearchResultRecord) -> str | None:
    text = f"{result.source_url} {result.title} {result.snippet}".lower()
    if " uk" in f" {text}" or "united kingdom" in text:
        return "United Kingdom"
    if " eu" in f" {text}" or "europe" in text:
        return "EU"
    if "netherlands" in text:
        return "Netherlands"
    return None
