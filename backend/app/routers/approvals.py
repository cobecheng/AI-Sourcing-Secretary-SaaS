from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["approvals"])


@router.get("/projects/{project_id}/approvals")
def list_project_approvals(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="approvals",
        action="list_project_approvals",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.post("/approvals/{approval_id}/approve")
def approve_request(approval_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="approvals",
        action="approve_request",
        mock_mode=get_settings().mock_mode,
        approval_id=approval_id,
        safety="approval records are required before any future outbound action",
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

