from pydantic import BaseModel, Field


class InboxSyncRequest(BaseModel):
    project_id: int


class SupplierReplyResponse(BaseModel):
    reply_id: int
    email_thread_id: int
    gmail_thread_id: str
    supplier_id: int
    supplier_name: str
    subject: str | None = None
    body: str
    received_at: str | None = None
    status: str
    missing_or_ambiguous_requests: list[str] = Field(default_factory=list)


class InboxSyncResponse(BaseModel):
    project_id: int
    mock_mode: bool
    provider: str
    synced_threads: int
    synced_replies: int
    cache_status: str
    replies: list[SupplierReplyResponse]
    safety: dict[str, object]


class ExtractReplyTermsResponse(BaseModel):
    supplier_term_id: int
    reply_id: int
    email_thread_id: int
    supplier_id: int
    moq: str | None = None
    price_list_available: bool | None = None
    payment_terms: str | None = None
    shipping_regions: dict | None = None
    lead_time: str | None = None
    account_requirements: str | None = None
    missing_or_ambiguous_requests: list[str]
    chat_message_id: int | None
    mock_mode: bool
    safety: dict[str, object]


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
