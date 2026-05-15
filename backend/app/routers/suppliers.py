from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["suppliers"])


@router.get("/projects/{project_id}/suppliers")
def list_project_suppliers(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="list_project_suppliers",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="get_supplier",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="update_supplier",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )

