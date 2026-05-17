from pydantic import BaseModel, Field


class DraftFollowupRequest(BaseModel):
    reply_text: str | None = Field(default=None, min_length=1)
    business_info: dict[str, str] | None = None


class FollowupDraftResponse(BaseModel):
    outreach_id: int
    approval_request_id: int
    email_thread_id: int
    project_id: int
    supplier_id: int
    supplier_name: str
    recipient: str | None
    subject: str
    body: str
    status: str
    missing_business_info: list[str]
    blocked_commitments: list[str]
    chat_message_id: int | None
    mock_mode: bool
    outbound_performed: bool
    safety: dict[str, object]
