from pydantic import BaseModel, Field

from app.schemas.search import SearchResultRecord


class SupplierEvidenceResponse(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    source_type: str | None = None


class SupplierScoreMetadata(BaseModel):
    confidence: float
    relevance_score: float
    trust_score: float
    routing_decision: str
    fallback_used: bool
    evidence_urls: list[str]
    normalized_domain: str


class SupplierResponse(BaseModel):
    id: int
    project_id: int
    name: str
    website: str | None = None
    country: str | None = None
    email: str | None = None
    supplier_type: str | None = None
    contact_method: str | None = None
    trust_score: float | None = None
    relevance_score: float | None = None
    status: str
    notes: str | None = None
    evidence: list[SupplierEvidenceResponse] = Field(default_factory=list)
    scoring_metadata: SupplierScoreMetadata | None = None


class ExtractSuppliersRequest(BaseModel):
    results: list[SearchResultRecord] | None = None


class ExtractSuppliersResponse(BaseModel):
    project_id: int
    candidates_seen: int
    suppliers_created: int
    suppliers_updated: int
    duplicates_merged: int
    mock_mode: bool
    suppliers: list[SupplierResponse]
    safety: dict[str, object]
