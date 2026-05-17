from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import (
    ApprovalRequest,
    AuditLog,
    ContactForm,
    FormSubmission,
    OutreachMessage,
    Supplier,
)
from app.schemas.outbound import (
    ApprovalEditRequest,
    ApprovalDecisionResponse,
    ApprovalRequestSummary,
    ExecuteEmailResponse,
    ExecuteFormResponse,
    ProjectApprovalsResponse,
)


BLOCKED_FORM_TERMS = {
    "captcha",
    "login",
    "payment",
    "document_upload",
    "document upload",
    "account_creation",
    "account creation",
    "legal_commitment",
    "legal commitment",
}

APPROVABLE_STATUSES = {"pending", "edited"}
FINAL_STATUSES = {"rejected", "expired", "cancelled"}


def list_project_approval_requests(db: Session, project_id: int) -> ProjectApprovalsResponse:
    approvals = db.scalars(
        select(ApprovalRequest).where(ApprovalRequest.project_id == project_id).order_by(ApprovalRequest.id)
    ).all()
    status_counts: dict[str, int] = {}
    for approval in approvals:
        status_counts[approval.status] = status_counts.get(approval.status, 0) + 1

    return ProjectApprovalsResponse(
        project_id=project_id,
        mock_mode=get_settings().mock_mode,
        status_counts=status_counts,
        items=[_approval_summary(approval) for approval in approvals],
    )


def approve_approval_request(
    db: Session,
    approval_id: int,
    user_id: int | None = None,
    note: str | None = None,
) -> ApprovalDecisionResponse:
    approval = _get_approval(db, approval_id)
    if approval.status == "approved":
        return _approval_response(approval)
    if approval.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"{approval.status.title()} approval requests cannot be approved")
    if approval.status not in APPROVABLE_STATUSES:
        raise HTTPException(status_code=409, detail=f"{approval.status.title()} approval requests cannot be approved")

    approval.status = "approved"
    approval.decision_json = {
        "decision": "approved",
        "note": note,
        "mock_mode": get_settings().mock_mode,
    }
    approval.decided_by_user_id = user_id
    approval.decided_at = datetime.now(UTC)
    _audit(
        db,
        project_id=approval.project_id,
        user_id=user_id,
        action="approval.approved",
        entity_type="approval_request",
        entity_id=approval.id,
        metadata={"request_type": approval.request_type},
    )
    db.commit()
    db.refresh(approval)
    return _approval_response(approval)


def reject_approval_request(
    db: Session,
    approval_id: int,
    user_id: int | None = None,
    note: str | None = None,
) -> ApprovalDecisionResponse:
    approval = _get_approval(db, approval_id)
    return _set_approval_decision(db, approval, "rejected", user_id, note)


def edit_approval_request(
    db: Session,
    approval_id: int,
    request: ApprovalEditRequest,
) -> ApprovalDecisionResponse:
    approval = _get_approval(db, approval_id)
    if approval.status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail=f"{approval.status.title()} approval requests cannot be edited")
    if not request.payload_json:
        raise HTTPException(status_code=422, detail="Edited approval payload cannot be empty")

    approval.payload_json = request.payload_json
    approval.status = "edited"
    approval.decision_json = {
        "decision": "edited",
        "note": request.note,
        "mock_mode": get_settings().mock_mode,
    }
    approval.decided_by_user_id = request.user_id
    approval.decided_at = datetime.now(UTC)
    _audit(
        db,
        project_id=approval.project_id,
        user_id=request.user_id,
        action="approval.edited",
        entity_type="approval_request",
        entity_id=approval.id,
        metadata={"request_type": approval.request_type, "payload_json": approval.payload_json},
    )
    db.commit()
    db.refresh(approval)
    return _approval_response(approval)


def expire_approval_request(
    db: Session,
    approval_id: int,
    user_id: int | None = None,
    note: str | None = None,
) -> ApprovalDecisionResponse:
    approval = _get_approval(db, approval_id)
    return _set_approval_decision(db, approval, "expired", user_id, note)


def cancel_approval_request(
    db: Session,
    approval_id: int,
    user_id: int | None = None,
    note: str | None = None,
) -> ApprovalDecisionResponse:
    approval = _get_approval(db, approval_id)
    return _set_approval_decision(db, approval, "cancelled", user_id, note)


def execute_approved_email(db: Session, outreach_id: int) -> ExecuteEmailResponse:
    outreach = db.get(OutreachMessage, outreach_id)
    if outreach is None:
        raise HTTPException(status_code=404, detail="Outreach message not found")

    approval = _get_approved_approval(
        db,
        project_id=outreach.project_id,
        supplier_id=outreach.supplier_id,
        request_types=("send_email", "email_send"),
    )
    idempotency_key = outreach.idempotency_key or f"email-send:{outreach.project_id}:{outreach.id}"

    if outreach.status == "sent_mock" and outreach.sent_at is not None:
        return ExecuteEmailResponse(
            action="send_email",
            status="idempotent_replay",
            approval_request_id=approval.id,
            outreach_id=outreach.id,
            idempotency_key=idempotency_key,
            mock_mode=True,
            outbound_performed=False,
            sent_at=outreach.sent_at.isoformat(),
            safety=_email_safety_payload(),
        )

    outreach.idempotency_key = idempotency_key
    outreach.status = "sent_mock"
    outreach.approved_by_user = True
    outreach.sent_at = datetime.now(UTC)
    _audit(
        db,
        project_id=outreach.project_id,
        user_id=approval.decided_by_user_id,
        action="outreach.email_sent_mock",
        entity_type="outreach_message",
        entity_id=outreach.id,
        metadata={"approval_request_id": approval.id, "idempotency_key": idempotency_key},
    )
    db.commit()
    db.refresh(outreach)
    return ExecuteEmailResponse(
        action="send_email",
        status=outreach.status,
        approval_request_id=approval.id,
        outreach_id=outreach.id,
        idempotency_key=idempotency_key,
        mock_mode=True,
        outbound_performed=False,
        sent_at=outreach.sent_at.isoformat() if outreach.sent_at else None,
        safety=_email_safety_payload(),
    )


def execute_approved_form_submission(db: Session, contact_form_id: int) -> ExecuteFormResponse:
    contact_form = db.get(ContactForm, contact_form_id)
    if contact_form is None:
        raise HTTPException(status_code=404, detail="Contact form not found")

    approval = _get_approved_approval(
        db,
        project_id=_project_id_for_supplier(db, contact_form.supplier_id),
        supplier_id=contact_form.supplier_id,
        request_types=("submit_contact_form", "contact_form_submit"),
    )
    _raise_if_form_blocked(contact_form, approval)

    idempotency_key = f"form-submit:{contact_form.id}:{approval.id}"
    existing = db.scalar(select(FormSubmission).where(FormSubmission.idempotency_key == idempotency_key))
    if existing is not None:
        return ExecuteFormResponse(
            action="submit_contact_form",
            status="idempotent_replay",
            approval_request_id=approval.id,
            form_submission_id=existing.id,
            contact_form_id=contact_form.id,
            idempotency_key=idempotency_key,
            mock_mode=True,
            outbound_performed=False,
            screenshot_before_url=existing.screenshot_before_url,
            screenshot_after_url=existing.screenshot_after_url,
            safety=_form_safety_payload(contact_form),
        )

    submission = FormSubmission(
        supplier_id=contact_form.supplier_id,
        contact_form_id=contact_form.id,
        submitted_payload_json=approval.payload_json,
        status="submitted_mock",
        approved_by_user=True,
        idempotency_key=idempotency_key,
        screenshot_before_url=f"mock://screenshots/contact-forms/{contact_form.id}/before.png",
        screenshot_after_url=f"mock://screenshots/contact-forms/{contact_form.id}/after.png",
        submitted_at=datetime.now(UTC),
    )
    db.add(submission)
    db.flush()
    _audit(
        db,
        project_id=approval.project_id,
        user_id=approval.decided_by_user_id,
        action="form.submitted_mock",
        entity_type="form_submission",
        entity_id=submission.id,
        metadata={"approval_request_id": approval.id, "idempotency_key": idempotency_key},
    )
    db.commit()
    db.refresh(submission)
    return ExecuteFormResponse(
        action="submit_contact_form",
        status=submission.status,
        approval_request_id=approval.id,
        form_submission_id=submission.id,
        contact_form_id=contact_form.id,
        idempotency_key=idempotency_key,
        mock_mode=True,
        outbound_performed=False,
        screenshot_before_url=submission.screenshot_before_url,
        screenshot_after_url=submission.screenshot_after_url,
        safety=_form_safety_payload(contact_form),
    )


def _get_approval(db: Session, approval_id: int) -> ApprovalRequest:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval


def _set_approval_decision(
    db: Session,
    approval: ApprovalRequest,
    status: str,
    user_id: int | None,
    note: str | None,
) -> ApprovalDecisionResponse:
    if approval.status == status:
        return _approval_response(approval)
    if approval.status == "approved" and status in FINAL_STATUSES:
        raise HTTPException(status_code=409, detail="Approved approval requests cannot be changed after approval")

    approval.status = status
    approval.decision_json = {
        "decision": status,
        "note": note,
        "mock_mode": get_settings().mock_mode,
    }
    approval.decided_by_user_id = user_id
    approval.decided_at = datetime.now(UTC)
    _audit(
        db,
        project_id=approval.project_id,
        user_id=user_id,
        action=f"approval.{status}",
        entity_type="approval_request",
        entity_id=approval.id,
        metadata={"request_type": approval.request_type},
    )
    db.commit()
    db.refresh(approval)
    return _approval_response(approval)


def _get_approved_approval(
    db: Session,
    project_id: int,
    supplier_id: int,
    request_types: tuple[str, ...],
) -> ApprovalRequest:
    approval = db.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.supplier_id == supplier_id,
            ApprovalRequest.request_type.in_(request_types),
            ApprovalRequest.status == "approved",
        )
        .order_by(ApprovalRequest.decided_at.desc(), ApprovalRequest.id.desc())
    )
    if approval is None:
        raise HTTPException(status_code=403, detail="Approved approval_request is required before outbound execution")
    return approval


def _project_id_for_supplier(db: Session, supplier_id: int) -> int:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier project not found")
    return supplier.project_id


def _raise_if_form_blocked(contact_form: ContactForm, approval: ApprovalRequest) -> None:
    fields_json = contact_form.fields_json or {}
    blocked_flags = set()
    if contact_form.requires_captcha:
        blocked_flags.add("captcha")
    if contact_form.requires_login:
        blocked_flags.add("login")

    payload_text = " ".join(str(value).lower() for value in _flatten_json(approval.payload_json))
    blocked_flags.update(term for term in BLOCKED_FORM_TERMS if term in payload_text)
    blocked_flags.update(term for term in BLOCKED_FORM_TERMS if term in str(fields_json).lower())
    if blocked_flags:
        raise HTTPException(
            status_code=409,
            detail=f"Contact form submission blocked by safety rule: {', '.join(sorted(blocked_flags))}",
        )


def _flatten_json(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten_json(child)]
    if isinstance(value, list):
        return [item for child in value for item in _flatten_json(child)]
    return [value]


def _audit(
    db: Session,
    project_id: int,
    user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    metadata: dict[str, Any],
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            project_id=project_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
        )
    )


def _approval_response(approval: ApprovalRequest) -> ApprovalDecisionResponse:
    return ApprovalDecisionResponse(
        id=approval.id,
        project_id=approval.project_id,
        supplier_id=approval.supplier_id,
        request_type=approval.request_type,
        status=approval.status,
        title=approval.title,
        payload_json=approval.payload_json,
        decision_json=approval.decision_json,
    )


def _approval_summary(approval: ApprovalRequest) -> ApprovalRequestSummary:
    return ApprovalRequestSummary(
        id=approval.id,
        project_id=approval.project_id,
        supplier_id=approval.supplier_id,
        request_type=approval.request_type,
        status=approval.status,
        title=approval.title,
        payload_json=approval.payload_json,
        decision_json=approval.decision_json,
        decided_by_user_id=approval.decided_by_user_id,
        decided_at=approval.decided_at.isoformat() if approval.decided_at else None,
        expires_at=approval.expires_at.isoformat() if approval.expires_at else None,
    )


def _email_safety_payload() -> dict[str, object]:
    return {
        "requires_approved_approval_request": True,
        "uses_idempotency_key": True,
        "real_gmail_send_enabled": False,
        "mock_mode": True,
    }


def _form_safety_payload(contact_form: ContactForm) -> dict[str, object]:
    return {
        "requires_approved_approval_request": True,
        "uses_idempotency_key": True,
        "screenshots_stored_when_possible": True,
        "real_browser_submission_enabled": False,
        "requires_captcha": contact_form.requires_captcha,
        "requires_login": contact_form.requires_login,
        "mock_mode": True,
    }
