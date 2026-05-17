from app.config import Settings, get_settings
from app.schemas.admin import AdminReadinessResponse, ProviderHealthResponse


def admin_readiness() -> AdminReadinessResponse:
    settings = get_settings()
    providers = [
        _provider(
            provider="search:exa",
            enabled=settings.enable_real_search and not settings.mock_mode,
            configured=bool(settings.exa_api_key),
            timeout_seconds=settings.search_request_timeout_seconds,
        ),
        _provider(
            provider="scraping:firecrawl",
            enabled=settings.enable_real_scraping and not settings.mock_mode,
            configured=bool(settings.firecrawl_api_key),
            timeout_seconds=settings.scraping_request_timeout_seconds,
        ),
        _provider(
            provider="llm:litellm",
            enabled=not settings.mock_mode,
            configured=bool(settings.litellm_proxy_url and settings.litellm_master_key),
            timeout_seconds=None,
        ),
    ]
    status = "ready" if all(item.status in {"ready", "disabled"} for item in providers) else "degraded_safe"
    return AdminReadinessResponse(
        environment=settings.app_env,
        mock_mode=settings.mock_mode,
        status=status,
        providers=providers,
        observability={
            "audit_log_enabled": True,
            "approval_decisions_audited": True,
            "outbound_execution_audited": True,
            "llm_usage_logged": True,
            "provider_health_endpoint": "/admin/readiness",
        },
        safety={
            "autonomous_outbound_actions": False,
            "requires_approval_request_for_outbound": True,
            "provider_failure_triggers_outbound": False,
            "mock_mode_default": True,
        },
    )


def production_hardening_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []
    if settings.app_env == "production" and settings.mock_mode:
        warnings.append("Production is running in mock mode; real providers are disabled.")
    if settings.app_env == "production" and not settings.database_url:
        warnings.append("DATABASE_URL is not configured.")
    if settings.enable_real_search and not settings.exa_api_key:
        warnings.append("Real search is enabled but EXA_API_KEY is missing.")
    if settings.enable_real_scraping and not settings.firecrawl_api_key:
        warnings.append("Real scraping is enabled but FIRECRAWL_API_KEY is missing.")
    if not settings.mock_mode and (not settings.litellm_proxy_url or not settings.litellm_master_key):
        warnings.append("Real model routing is enabled but LiteLLM credentials are incomplete.")
    return warnings


def _provider(
    provider: str,
    enabled: bool,
    configured: bool,
    timeout_seconds: int | None,
) -> ProviderHealthResponse:
    notes: list[str] = []
    if not enabled:
        status = "disabled"
        notes.append("Provider is disabled by mock mode or feature flag.")
    elif configured:
        status = "ready"
        notes.append("Provider credentials are configured. Live ping is intentionally skipped to avoid paid calls.")
    else:
        status = "degraded_safe"
        notes.append("Provider is enabled but credentials are missing; callers must use mock fallback or return safe errors.")
    if timeout_seconds is not None:
        notes.append(f"Configured timeout: {timeout_seconds}s.")
    return ProviderHealthResponse(
        provider=provider,
        enabled=enabled,
        configured=configured,
        status=status,
        safe_degradation="No browser submission, email send, or paid call is triggered by this health check.",
        outbound_actions_allowed=False,
        notes=notes,
    )
