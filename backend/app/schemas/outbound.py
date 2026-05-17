from pydantic import BaseModel, Field


class ApprovalDecisionRequest(BaseModel):
    user_id: int | None = None
    note: str | None = None


class ApprovalDecisionResponse(BaseModel):
    id: int
    project_id: int
    supplier_id: int | None
    request_type: str
    status: str
    title: str
    decision_json: dict | None


class ExecuteOutboundResponse(BaseModel):
    action: str
    status: str
    approval_request_id: int
    idempotency_key: str
    mock_mode: bool
    outbound_performed: bool
    safety: dict[str, object]


class ExecuteEmailResponse(ExecuteOutboundResponse):
    outreach_id: int
    sent_at: str | None


class ExecuteFormResponse(ExecuteOutboundResponse):
    form_submission_id: int
    contact_form_id: int
    screenshot_before_url: str | None
    screenshot_after_url: str | None
