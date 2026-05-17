from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.forms import ContactFormResponse, InspectSupplierFormsRequest, InspectSupplierFormsResponse
from app.schemas.outbound import ExecuteFormResponse
from app.services.form_inspection import inspect_supplier_forms, list_contact_forms
from app.services.outbound_actions import execute_approved_form_submission


router = APIRouter(tags=["forms"])


@router.post("/suppliers/{supplier_id}/forms/inspect", response_model=InspectSupplierFormsResponse)
def inspect_supplier_forms_endpoint(
    supplier_id: int,
    request: InspectSupplierFormsRequest | None = None,
    db: Session = Depends(get_db),
) -> InspectSupplierFormsResponse:
    return inspect_supplier_forms(
        db,
        supplier_id=supplier_id,
        form_url=request.form_url if request else None,
        page_text=request.page_text if request else None,
    )


@router.get("/suppliers/{supplier_id}/forms", response_model=list[ContactFormResponse])
def list_supplier_forms_endpoint(supplier_id: int, db: Session = Depends(get_db)) -> list[ContactFormResponse]:
    return list_contact_forms(db, supplier_id)


@router.post("/forms/{form_id}/prepare-submission")
def prepare_form_submission(form_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="prepare_form_submission",
        mock_mode=get_settings().mock_mode,
        form_id=form_id,
    )


@router.post("/forms/{form_id}/approve-submit", response_model=ExecuteFormResponse)
def approve_form_submission(form_id: int, db: Session = Depends(get_db)) -> ExecuteFormResponse:
    return execute_approved_form_submission(db, form_id)


@router.post("/forms/{form_id}/reject")
def reject_form_submission(form_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="forms",
        action="reject_form_submission",
        mock_mode=get_settings().mock_mode,
        form_id=form_id,
    )
