from typing import Any

from pydantic import BaseModel, Field


class LLMCompleteRequest(BaseModel):
    project_id: int
    task_type: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    input_json: dict[str, Any] | None = None
    required_output_fields: list[str] = Field(default_factory=list)
    provider: str | None = None
    model: str | None = None
    input_tokens: int = Field(default=240, ge=0)
    output_tokens: int = Field(default=120, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(default=10, ge=0)
    confidence: float | None = Field(default=None, ge=0, le=1)
    prompt_version: str | None = None
    schema_version: str | None = None


class AgentRunUsageResponse(BaseModel):
    id: int
    project_id: int
    task_type: str
    status: str
    provider: str | None
    model: str | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    actual_cost_usd: float | None
    latency_ms: int | None
    prompt_version: str | None
    schema_version: str | None
    confidence: float | None
    fallback_used: bool


class LLMBudgetResponse(BaseModel):
    id: int
    user_id: int
    project_id: int | None
    daily_limit_usd: float
    monthly_limit_usd: float
    project_limit_usd: float
    premium_call_limit: int
    current_daily_spend_usd: float
    current_monthly_spend_usd: float
    current_project_spend_usd: float
    project_budget_ratio: float
    status: str


class LLMUsageResponse(BaseModel):
    scope: str
    id: int
    budget: LLMBudgetResponse | None
    total_estimated_cost_usd: float
    total_actual_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    runs: list[AgentRunUsageResponse]


class LLMCompleteResponse(BaseModel):
    agent_run: AgentRunUsageResponse | None
    budget: LLMBudgetResponse
    status: str
    message: str
    routing: dict[str, Any]
    chat_warning_created: bool
    requires_user_approval: bool


class LLMModelConfigResponse(BaseModel):
    id: int | None
    task_type: str
    tier: int
    provider: str
    model: str
    priority: int
    max_input_tokens: int | None
    max_output_tokens: int | None
    max_cost_usd: float | None
    enabled: bool
    fallback_tier: int | None = None
    schema_version: str
