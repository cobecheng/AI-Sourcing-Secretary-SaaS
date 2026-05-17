from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.inbox import DraftFollowupRequest, FollowupDraftResponse
from app.services.followup_drafting import draft_followup_reply


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


@router.post("/replies/{reply_id}/draft-followup", response_model=FollowupDraftResponse)
def draft_reply_followup(
    reply_id: int,
    request: DraftFollowupRequest | None = None,
    db: Session = Depends(get_db),
) -> FollowupDraftResponse:
    return draft_followup_reply(db, reply_id, request)
