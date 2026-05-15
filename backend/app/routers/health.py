from fastapi import APIRouter
from typing import Any

from app.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, Any]:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "environment": settings.app_env,
        "mock_mode": settings.mock_mode,
        "status": "ok",
        "integrations": {
            "database_configured": bool(settings.database_url),
            "redis_configured": bool(settings.redis_url),
            "exa_configured": bool(settings.exa_api_key),
            "firecrawl_configured": bool(settings.firecrawl_api_key),
            "litellm_configured": bool(settings.litellm_proxy_url),
        },
    }
