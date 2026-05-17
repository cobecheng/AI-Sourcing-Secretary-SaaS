from pydantic import BaseModel, Field


class InspectSupplierFormsRequest(BaseModel):
    form_url: str | None = None
    page_text: str | None = None


class ContactFormFieldResponse(BaseModel):
    name: str
    label: str
    field_type: str
    required: bool
    mapped_memory_key: str | None = None
    has_value: bool = False


class ContactFormResponse(BaseModel):
    id: int
    supplier_id: int
    form_url: str
    form_type: str | None
    fields: list[ContactFormFieldResponse]
    required_missing_fields: list[str]
    requires_captcha: bool
    requires_login: bool
    status: str
    safety_flags: list[str] = Field(default_factory=list)


class InspectSupplierFormsResponse(BaseModel):
    supplier_id: int
    forms: list[ContactFormResponse]
    chat_message_id: int | None
    paused_for_review: bool
    mock_mode: bool
    safety: dict[str, object]
