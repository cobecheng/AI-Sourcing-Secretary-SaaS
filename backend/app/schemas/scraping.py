from pydantic import BaseModel, Field


class ScrapeSupplierRequest(BaseModel):
    url: str | None = Field(default=None, description="Optional page URL. Defaults to the supplier website.")


class SupplierSourceResponse(BaseModel):
    id: int
    supplier_id: int
    url: str
    title: str | None = None
    snippet: str | None = None
    extracted_text: str | None = None
    source_type: str | None = None


class ScrapeSupplierResponse(BaseModel):
    supplier_id: int
    source: SupplierSourceResponse
    provider: str
    mock_mode: bool
    cache_status: str
    content_length: int
    safety: dict[str, object]
