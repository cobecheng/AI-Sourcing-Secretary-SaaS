from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Sourcing Secretary API"
    app_env: str = "development"
    mock_mode: bool = True
    database_url: str = ""
    redis_url: str = ""
    cors_origins: list[str] = ["http://localhost:3000"]
    exa_api_key: str = ""
    enable_real_search: bool = False
    search_provider: str = "exa"
    search_request_timeout_seconds: int = 20
    max_search_results: int = 10
    firecrawl_api_key: str = ""
    enable_real_scraping: bool = False
    scraping_provider: str = "firecrawl"
    scraping_rate_limit_per_minute: int = 10
    scraping_request_timeout_seconds: int = 20
    scraping_user_agent: str = "AI-Sourcing-Secretary/0.1 (+mock-safe development crawler)"
    max_suppliers_to_scrape: int = 10
    litellm_proxy_url: str = ""
    litellm_master_key: str = ""
    max_project_llm_cost_usd: float = 5
    max_user_daily_llm_cost_usd: float = 2
    max_premium_calls_per_project: int = 5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
