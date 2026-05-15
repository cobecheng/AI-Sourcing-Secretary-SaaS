from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(prefix="/projects/{project_id}/research", tags=["research"])


@router.post("/start")
def start_research(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="research",
        action="start_research",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/status")
def get_research_status(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="research",
        action="get_research_status",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )

