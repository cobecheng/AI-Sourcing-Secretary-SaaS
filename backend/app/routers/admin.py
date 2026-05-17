from fastapi import APIRouter

from app.schemas.admin import AdminReadinessResponse
from app.services.admin_readiness import admin_readiness


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/readiness", response_model=AdminReadinessResponse)
def get_admin_readiness() -> AdminReadinessResponse:
    return admin_readiness()
