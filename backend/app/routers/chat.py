from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(prefix="/projects/{project_id}", tags=["chat"])


@router.post("/chat")
def post_chat_message(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="chat",
        action="post_chat_message",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/messages")
def list_project_messages(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="chat",
        action="list_project_messages",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )

