from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["milestones"])


@router.get("/projects/{project_id}/milestones")
def list_project_milestones(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="milestones",
        action="list_project_milestones",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.post("/projects/{project_id}/milestones")
def create_project_milestone(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="milestones",
        action="create_project_milestone",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.patch("/milestones/{milestone_id}")
def update_milestone(milestone_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="milestones",
        action="update_milestone",
        mock_mode=get_settings().mock_mode,
        milestone_id=milestone_id,
    )

