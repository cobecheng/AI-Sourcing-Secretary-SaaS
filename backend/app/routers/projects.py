from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project() -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="create_project",
        mock_mode=get_settings().mock_mode,
    )


@router.get("")
def list_projects() -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="list_projects",
        mock_mode=get_settings().mock_mode,
    )


@router.get("/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="get_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.patch("/{project_id}")
def update_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="update_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="delete_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )

