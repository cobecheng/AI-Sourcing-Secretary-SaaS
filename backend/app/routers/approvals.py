from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.outbound import ApprovalDecisionRequest, ApprovalDecisionResponse
from app.services.outbound_actions import approve_approval_request


router = APIRouter(tags=["approvals"])


@router.get("/projects/{project_id}/approvals")
def list_project_approvals(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="approvals",
        action="list_project_approvals",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.post("/approvals/{approval_id}/approve", response_model=ApprovalDecisionResponse)
def approve_request(
    approval_id: int,
    request: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    return approve_approval_request(
        db,
        approval_id=approval_id,
        user_id=request.user_id if request else None,
        note=request.note if request else None,
    )


@router.post("/approvals/{approval_id}/reject")
def reject_request(approval_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="approvals",
        action="reject_request",
        mock_mode=get_settings().mock_mode,
        approval_id=approval_id,
    )


@router.patch("/approvals/{approval_id}/edit")
def edit_request(approval_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="approvals",
        action="edit_request",
        mock_mode=get_settings().mock_mode,
        approval_id=approval_id,
    )
