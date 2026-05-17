from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.outbound import ExecuteEmailResponse
from app.schemas.outreach import DraftOutreachRequest, OutreachDraftResponse, PendingOutreachResponse
from app.services.outreach_drafting import draft_supplier_email, list_pending_outreach as list_pending_outreach_service
from app.services.outbound_actions import execute_approved_email


router = APIRouter(tags=["outreach"])


@router.post("/suppliers/{supplier_id}/outreach/draft", response_model=OutreachDraftResponse)
def draft_supplier_outreach(
    supplier_id: int,
    request: DraftOutreachRequest | None = None,
    db: Session = Depends(get_db),
) -> OutreachDraftResponse:
    return draft_supplier_email(db, supplier_id, request)


@router.get("/projects/{project_id}/outreach/pending", response_model=PendingOutreachResponse)
def list_pending_outreach(project_id: int, db: Session = Depends(get_db)) -> PendingOutreachResponse:
    return list_pending_outreach_service(db, project_id)


@router.post("/outreach/{outreach_id}/approve-send", response_model=ExecuteEmailResponse)
def approve_send_outreach(outreach_id: int, db: Session = Depends(get_db)) -> ExecuteEmailResponse:
    return execute_approved_email(db, outreach_id)


@router.post("/outreach/{outreach_id}/reject")
def reject_outreach(outreach_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="outreach",
        action="reject_outreach",
        mock_mode=get_settings().mock_mode,
        outreach_id=outreach_id,
    )


@router.patch("/outreach/{outreach_id}")
def update_outreach(outreach_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="outreach",
        action="update_outreach",
        mock_mode=get_settings().mock_mode,
        outreach_id=outreach_id,
    )
