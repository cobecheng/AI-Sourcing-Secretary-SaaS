from pydantic import BaseModel


class MilestoneSummary(BaseModel):
    id: int
    name: str
    status: str
    summary: str | None = None
    metadata_json: dict | None = None


class SupplierEvidenceSummary(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    source_type: str | None = None


class SupplierSummary(BaseModel):
    id: int
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
    evidence: list[SupplierEvidenceSummary]


class ApprovalSummary(BaseModel):
    id: int
    supplier_id: int | None
    request_type: str
    status: str
    title: str
    payload_json: dict


class WorkflowSummary(BaseModel):
    id: int
    workflow_name: str
    current_node: str | None
    status: str
    idempotency_key: str


class ResearchStatusResponse(BaseModel):
    project_id: int
    project_status: str
    mock_mode: bool
    workflow: WorkflowSummary | None
    milestones: list[MilestoneSummary]
    suppliers: list[SupplierSummary]
    approvals: list[ApprovalSummary]


class MockResearchStartResponse(ResearchStatusResponse):
    message: str
