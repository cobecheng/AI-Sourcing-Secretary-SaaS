from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Sourcing Secretary API"
    app_env: str = "development"
    mock_mode: bool = True
    database_url: str = ""
    redis_url: str = ""
    max_project_llm_cost_usd: float = 5
    max_user_daily_llm_cost_usd: float = 2
    max_premium_calls_per_project: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

