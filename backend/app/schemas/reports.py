from pydantic import BaseModel, Field


class SupplierReportTerm(BaseModel):
    moq: str | None = None
    price_list_available: bool | None = None
    payment_terms: str | None = None
    shipping_regions: dict | None = None
    lead_time: str | None = None
    account_requirements: str | None = None


class SupplierReportItem(BaseModel):
    supplier_id: int
    name: str
    website: str | None = None
    status: str
    contact_method: str | None = None
    trust_score: float | None = None
    relevance_score: float | None = None
    terms: SupplierReportTerm | None = None
    evidence_urls: list[str] = Field(default_factory=list)
    recommendation: str


class ProjectReportResponse(BaseModel):
    project_id: int
    mock_mode: bool
    status: str
    summary: str
    suppliers: list[SupplierReportItem]
    model_routing: dict[str, object]
    safety: dict[str, object]
