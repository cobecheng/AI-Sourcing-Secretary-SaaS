from pydantic import BaseModel, Field


class DraftOutreachRequest(BaseModel):
    business_info: dict[str, str] | None = Field(
        default=None,
        description="Optional user-provided business facts to store before drafting.",
    )


class OutreachEvidence(BaseModel):
    url: str
    title: str | None = None
    snippet: str | None = None
    source_type: str | None = None


class OutreachDraftResponse(BaseModel):
    outreach_id: int
    approval_request_id: int
    project_id: int
    supplier_id: int
    supplier_name: str
    recipient: str | None
    subject: str
    body: str
    status: str
    missing_business_info: list[str]
    hallucination_flags: list[str]
    evidence: list[OutreachEvidence]
    chat_message_id: int | None
    mock_mode: bool
    outbound_performed: bool
    safety: dict[str, object]


class PendingOutreachItem(BaseModel):
    outreach_id: int
    approval_request_id: int | None
    supplier_id: int
    supplier_name: str
    recipient: str | None
    subject: str | None
    status: str
    missing_business_info: list[str]
    evidence: list[OutreachEvidence]


class PendingOutreachResponse(BaseModel):
    project_id: int
    mock_mode: bool
    outbound_performed: bool
    items: list[PendingOutreachItem]
