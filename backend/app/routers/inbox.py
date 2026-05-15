from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["inbox"])


@router.post("/inbox/sync")
def sync_inbox() -> dict[str, Any]:
    return placeholder_response(
        area="inbox",
        action="sync_inbox",
        mock_mode=get_settings().mock_mode,
        safety="future implementation must be explicit and idempotent",
    )


@router.get("/projects/{project_id}/replies")
def list_project_replies(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="inbox",
        action="list_project_replies",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.post("/replies/{reply_id}/extract")
def extract_reply_terms(reply_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="inbox",
        action="extract_reply_terms",
        mock_mode=get_settings().mock_mode,
        reply_id=reply_id,
    )


@router.post("/replies/{reply_id}/draft-followup")
def draft_reply_followup(reply_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="inbox",
        action="draft_reply_followup",
        mock_mode=get_settings().mock_mode,
        reply_id=reply_id,
        safety="future follow-up sends require user approval",
    )

