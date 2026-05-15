from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(tags=["forms"])


@router.post("/suppliers/{supplier_id}/forms/inspect")
def inspect_supplier_forms(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="inspect_supplier_forms",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )


@router.get("/suppliers/{supplier_id}/forms")
def list_supplier_forms(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="list_supplier_forms",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )


@router.post("/forms/{form_id}/prepare-submission")
def prepare_form_submission(form_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="prepare_form_submission",
        mock_mode=get_settings().mock_mode,
        form_id=form_id,
    )


@router.post("/forms/{form_id}/approve-submit")
def approve_form_submission(form_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="approve_form_submission",
        mock_mode=get_settings().mock_mode,
        form_id=form_id,
        safety="requires approved approval_request before future implementation submits anything",
    )


@router.post("/forms/{form_id}/reject")
def reject_form_submission(form_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="reject_form_submission",
        mock_mode=get_settings().mock_mode,
        form_id=form_id,
    )

