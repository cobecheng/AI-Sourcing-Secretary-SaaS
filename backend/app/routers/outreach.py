from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["outreach"])


@router.post("/suppliers/{supplier_id}/outreach/draft")
def draft_supplier_outreach(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="outreach",
        action="draft_supplier_outreach",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )


@router.get("/projects/{project_id}/outreach/pending")
def list_pending_outreach(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="outreach",
        action="list_pending_outreach",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.post("/outreach/{outreach_id}/approve-send")
def approve_send_outreach(outreach_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="outreach",
        action="approve_send_outreach",
        mock_mode=get_settings().mock_mode,
        outreach_id=outreach_id,
        safety="future implementation must require approved approval_request and idempotency key",
    )


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

