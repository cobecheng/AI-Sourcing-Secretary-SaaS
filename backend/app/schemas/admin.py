from pydantic import BaseModel


class ProviderHealthResponse(BaseModel):
    provider: str
    enabled: bool
    configured: bool
    status: str
    safe_degradation: str
    outbound_actions_allowed: bool
    notes: list[str]


class AdminReadinessResponse(BaseModel):
    environment: str
    mock_mode: bool
    status: str
    providers: list[ProviderHealthResponse]
    observability: dict[str, object]
    safety: dict[str, object]
