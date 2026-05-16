from pydantic import BaseModel, Field


class CreateProjectFromChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_email: str = "mock-user@example.test"
    user_name: str | None = "Mock Retailer"


class ProjectFromChatResponse(BaseModel):
    project_id: int
    conversation_id: int
    user_id: int
    project_name: str
    status: str
    created_message_ids: list[int]
    milestone_ids: list[int]
    missing_business_info: list[str]


class ProjectSummaryResponse(BaseModel):
    id: int
    name: str
    status: str
    supplier_count: int
    pending_approvals: int
    unread_replies: int


class ChatMessageResponse(BaseModel):
    id: int
    sender: str
    message_type: str
    content: str
    metadata_json: dict | None = None


class ProjectMessagesResponse(BaseModel):
    project_id: int
    conversation_id: int
    messages: list[ChatMessageResponse]
