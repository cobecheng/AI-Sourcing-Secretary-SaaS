from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.inbox import (
    DraftFollowupRequest,
    ExtractReplyTermsResponse,
    FollowupDraftResponse,
    InboxSyncRequest,
    InboxSyncResponse,
    SupplierReplyResponse,
)
from app.services.followup_drafting import draft_followup_reply
from app.services.inbox_sync import extract_reply_terms as extract_reply_terms_service
from app.services.inbox_sync import list_project_replies as list_project_replies_service
from app.services.inbox_sync import sync_inbox as sync_inbox_service


router = APIRouter(tags=["inbox"])


@router.post("/inbox/sync", response_model=InboxSyncResponse)
def sync_inbox(request: InboxSyncRequest, db: Session = Depends(get_db)) -> InboxSyncResponse:
    return sync_inbox_service(db, request.project_id)


@router.get("/projects/{project_id}/replies", response_model=list[SupplierReplyResponse])
def list_project_replies(project_id: int, db: Session = Depends(get_db)) -> list[SupplierReplyResponse]:
    return list_project_replies_service(db, project_id)


@router.post("/replies/{reply_id}/extract", response_model=ExtractReplyTermsResponse)
def extract_reply_terms(reply_id: int, db: Session = Depends(get_db)) -> ExtractReplyTermsResponse:
    return extract_reply_terms_service(db, reply_id)


@router.post("/replies/{reply_id}/draft-followup", response_model=FollowupDraftResponse)
def draft_reply_followup(
    reply_id: int,
    request: DraftFollowupRequest | None = None,
    db: Session = Depends(get_db),
) -> FollowupDraftResponse:
    return draft_followup_reply(db, reply_id, request)
