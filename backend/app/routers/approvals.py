from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.outbound import ApprovalDecisionRequest, ApprovalDecisionResponse, ApprovalEditRequest, ProjectApprovalsResponse
from app.services.outbound_actions import (
    approve_approval_request,
    cancel_approval_request,
    edit_approval_request,
    expire_approval_request,
    list_project_approval_requests,
    reject_approval_request,
)


router = APIRouter(tags=["approvals"])


@router.get("/projects/{project_id}/approvals", response_model=ProjectApprovalsResponse)
def list_project_approvals(project_id: int, db: Session = Depends(get_db)) -> ProjectApprovalsResponse:
    return list_project_approval_requests(db, project_id)


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


@router.post("/approvals/{approval_id}/reject", response_model=ApprovalDecisionResponse)
def reject_request(
    approval_id: int,
    request: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    return reject_approval_request(
        db,
        approval_id=approval_id,
        user_id=request.user_id if request else None,
        note=request.note if request else None,
    )


@router.patch("/approvals/{approval_id}/edit", response_model=ApprovalDecisionResponse)
def edit_request(
    approval_id: int,
    request: ApprovalEditRequest,
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    return edit_approval_request(db, approval_id, request)


@router.post("/approvals/{approval_id}/expire", response_model=ApprovalDecisionResponse)
def expire_request(
    approval_id: int,
    request: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    return expire_approval_request(
        db,
        approval_id=approval_id,
        user_id=request.user_id if request else None,
        note=request.note if request else None,
    )


@router.post("/approvals/{approval_id}/cancel", response_model=ApprovalDecisionResponse)
def cancel_request(
    approval_id: int,
    request: ApprovalDecisionRequest | None = None,
    db: Session = Depends(get_db),
) -> ApprovalDecisionResponse:
    return cancel_approval_request(
        db,
        approval_id=approval_id,
        user_id=request.user_id if request else None,
        note=request.note if request else None,
    )
