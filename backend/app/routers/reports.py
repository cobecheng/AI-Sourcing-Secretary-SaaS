from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["reports"])


@router.post("/projects/{project_id}/report/generate")
def generate_project_report(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="reports",
        action="generate_project_report",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/projects/{project_id}/report")
def get_project_report(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="reports",
        action="get_project_report",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/projects/{project_id}/export.csv")
def export_project_csv(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="reports",
        action="export_project_csv",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )

