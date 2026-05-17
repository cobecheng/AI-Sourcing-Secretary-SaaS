from pydantic import BaseModel, Field


class SearchSuppliersRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int | None = Field(default=None, ge=1, le=25)


class SearchResultRecord(BaseModel):
    source_url: str
    title: str
    snippet: str
    query: str
    provider: str
    rank: int


class SearchSuppliersResponse(BaseModel):
    project_id: int
    query: str
    provider: str
    mock_mode: bool
    cache_status: str
    fallback_reason: str | None = None
    results: list[SearchResultRecord]
    safety: dict[str, object]
