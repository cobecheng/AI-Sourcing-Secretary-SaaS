from fastapi import APIRouter

from app.config import get_settings


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str | bool]:
    settings = get_settings()
    return {
        "app": settings.app_name,
        "environment": settings.app_env,
        "mock_mode": settings.mock_mode,
        "status": "ok",
    }

