from pydantic import BaseModel, Field


class LLMCompleteRequest(BaseModel):
    project_id: int
    task_type: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    provider: str = "mock"
    model: str = "mock-cheap"
    input_tokens: int = Field(default=240, ge=0)
    output_tokens: int = Field(default=120, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0)
    actual_cost_usd: float | None = Field(default=None, ge=0)
    latency_ms: int = Field(default=10, ge=0)
    confidence: float = Field(default=0.95, ge=0, le=1)
    fallback_used: bool = False


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
    chat_warning_created: bool
    requires_user_approval: bool
