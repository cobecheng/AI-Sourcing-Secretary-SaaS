from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ApprovalRequest, ChatMessage, Conversation, OutreachMessage, ProjectMemory, Supplier, SupplierSource
from app.schemas.outreach import (
    DraftOutreachRequest,
    OutreachDraftResponse,
    OutreachEvidence,
    PendingOutreachItem,
    PendingOutreachResponse,
)


REQUIRED_BUSINESS_FIELDS: dict[str, str] = {
    "business_name": "business name",
    "contact_name": "contact name",
    "business_email": "business email",
    "store_website": "store website",
    "country": "country",
    "monthly_order_size": "expected monthly order size",
}


def draft_supplier_email(
    db: Session,
    supplier_id: int,
    request: DraftOutreachRequest | None = None,
) -> OutreachDraftResponse:
    supplier = _get_supplier(db, supplier_id)
    business_info = _business_info(db, supplier.project_id)
    if request and request.business_info:
        business_info = _store_business_info(db, supplier.project_id, request.business_info)

    evidence = _supplier_evidence(db, supplier.id)
    missing = _missing_business_fields(business_info)
    subject = _draft_subject(supplier)
    body = _draft_body(supplier, business_info, missing, evidence)
    flags = _hallucination_flags(body, business_info)

    outreach = _upsert_outreach(db, supplier, subject, body)
    approval = _upsert_email_approval(db, supplier, outreach, missing, flags, evidence)
    chat_message = _upsert_missing_info_prompt(db, supplier.project_id, missing, supplier.name)

    db.commit()
    db.refresh(outreach)
    db.refresh(approval)
    if chat_message is not None:
        db.refresh(chat_message)

    return OutreachDraftResponse(
        outreach_id=outreach.id,
        approval_request_id=approval.id,
        project_id=outreach.project_id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        recipient=supplier.email,
        subject=subject,
        body=body,
        status=outreach.status,
        missing_business_info=missing,
        hallucination_flags=flags,
        evidence=evidence,
        chat_message_id=chat_message.id if chat_message else None,
        mock_mode=get_settings().mock_mode,
        outbound_performed=False,
        safety=_draft_safety(),
    )


def list_pending_outreach(db: Session, project_id: int) -> PendingOutreachResponse:
    items: list[PendingOutreachItem] = []
    outreach_messages = db.scalars(
        select(OutreachMessage)
        .where(
            OutreachMessage.project_id == project_id,
            OutreachMessage.channel == "email",
            OutreachMessage.status.in_(("draft", "pending_approval")),
        )
        .order_by(OutreachMessage.id)
    ).all()

    for outreach in outreach_messages:
        supplier = db.get(Supplier, outreach.supplier_id)
        if supplier is None:
            continue
        approval = _email_approval(db, outreach.project_id, supplier.id)
        payload = approval.payload_json if approval is not None else {}
        items.append(
            PendingOutreachItem(
                outreach_id=outreach.id,
                approval_request_id=approval.id if approval else None,
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                recipient=supplier.email,
                subject=outreach.subject,
                status=outreach.status,
                missing_business_info=list(payload.get("missing_fields", [])),
                evidence=_supplier_evidence(db, supplier.id),
            )
        )

    return PendingOutreachResponse(
        project_id=project_id,
        mock_mode=get_settings().mock_mode,
        outbound_performed=False,
        items=items,
    )


def _get_supplier(db: Session, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


def _business_info(db: Session, project_id: int) -> dict[str, str]:
    memory = db.scalar(
        select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "provided_business_info")
    )
    if memory is None:
        return {}
    return {str(key): str(value) for key, value in memory.value.items() if value}


def _store_business_info(db: Session, project_id: int, business_info: dict[str, str]) -> dict[str, str]:
    clean_info = {key: value.strip() for key, value in business_info.items() if isinstance(value, str) and value.strip()}
    memory = db.scalar(
        select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "provided_business_info")
    )
    if memory is None:
        memory = ProjectMemory(project_id=project_id, key="provided_business_info", value=clean_info)
        db.add(memory)
    else:
        memory.value = {**memory.value, **clean_info}
    db.flush()
    return {str(key): str(value) for key, value in memory.value.items() if value}


def _missing_business_fields(business_info: dict[str, str]) -> list[str]:
    return [label for key, label in REQUIRED_BUSINESS_FIELDS.items() if not business_info.get(key)]


def _supplier_evidence(db: Session, supplier_id: int) -> list[OutreachEvidence]:
    sources = db.scalars(select(SupplierSource).where(SupplierSource.supplier_id == supplier_id).order_by(SupplierSource.id)).all()
    return [
        OutreachEvidence(
            url=source.url,
            title=source.title,
            snippet=source.snippet,
            source_type=source.source_type,
        )
        for source in sources
    ]


def _draft_subject(supplier: Supplier) -> str:
    product_hint = "Pokemon TCG"
    return f"Wholesale {product_hint} account inquiry"


def _draft_body(
    supplier: Supplier,
    business_info: dict[str, str],
    missing: list[str],
    evidence: list[OutreachEvidence],
) -> str:
    greeting = f"Hello {supplier.name},"
    lines = [
        greeting,
        "",
        "I am interested in wholesale access for Pokemon TCG sealed products, including booster boxes and ETBs.",
    ]
    if business_info.get("business_name"):
        lines.append(f"Business name: {business_info['business_name']}")
    if business_info.get("contact_name"):
        lines.append(f"Contact name: {business_info['contact_name']}")
    if business_info.get("business_email"):
        lines.append(f"Business email: {business_info['business_email']}")
    if business_info.get("store_website"):
        lines.append(f"Store website: {business_info['store_website']}")
    if business_info.get("country"):
        lines.append(f"Country: {business_info['country']}")
    if business_info.get("monthly_order_size"):
        lines.append(f"Expected monthly order size: {business_info['monthly_order_size']}")

    lines.extend(
        [
            "",
            "Could you share your trade account requirements, MOQ, price list availability, and shipping terms?",
        ]
    )
    if missing:
        lines.extend(
            [
                "",
                "Details I still need before sending:",
                *[f"- {field}" for field in missing],
            ]
        )
    if evidence:
        lines.extend(
            [
                "",
                "Supplier evidence reviewed:",
                *[f"- {item.title or 'Supplier source'}: {item.url}" for item in evidence],
            ]
        )
    signature = business_info.get("contact_name") or "[contact name needed]"
    lines.extend(["", "Best,", signature])
    return "\n".join(lines)


def _hallucination_flags(body: str, business_info: dict[str, str]) -> list[str]:
    known_values = {value.lower() for value in business_info.values() if value}
    unsupported_phrases = {
        "small retail business": "Unsupported business-size claim",
        "mock retailer": "Unsupported business identity",
        "limited company": "Unsupported legal-entity claim",
        "vat registered": "Unsupported tax-status claim",
    }
    flags: list[str] = []
    lower_body = body.lower()
    for phrase, label in unsupported_phrases.items():
        if phrase in lower_body and phrase not in known_values:
            flags.append(label)
    return flags


def _upsert_outreach(db: Session, supplier: Supplier, subject: str, body: str) -> OutreachMessage:
    outreach = db.scalar(
        select(OutreachMessage)
        .where(
            OutreachMessage.project_id == supplier.project_id,
            OutreachMessage.supplier_id == supplier.id,
            OutreachMessage.channel == "email",
            OutreachMessage.status.in_(("draft", "pending_approval")),
        )
        .order_by(OutreachMessage.id)
    )
    if outreach is None:
        outreach = OutreachMessage(
            project_id=supplier.project_id,
            supplier_id=supplier.id,
            channel="email",
            idempotency_key=f"email-draft:{supplier.project_id}:{supplier.id}",
        )
        db.add(outreach)
    outreach.subject = subject
    outreach.body = body
    outreach.status = "pending_approval"
    outreach.approved_by_user = False
    outreach.sent_at = None
    db.flush()
    return outreach


def _upsert_email_approval(
    db: Session,
    supplier: Supplier,
    outreach: OutreachMessage,
    missing: list[str],
    flags: list[str],
    evidence: list[OutreachEvidence],
) -> ApprovalRequest:
    approval = _email_approval(db, outreach.project_id, supplier.id)
    if approval is None:
        approval = ApprovalRequest(project_id=outreach.project_id, supplier_id=supplier.id, request_type="send_email")
        db.add(approval)
    approval.status = "pending"
    approval.title = f"Approve supplier email draft to {supplier.name}"
    approval.payload_json = {
        "action": "send_email",
        "channel": "email",
        "mock_mode": get_settings().mock_mode,
        "outbound_actions_performed": 0,
        "outreach_id": outreach.id,
        "recipient": supplier.email,
        "subject": outreach.subject,
        "body": outreach.body,
        "missing_fields": missing,
        "hallucination_flags": flags,
        "evidence": [item.model_dump() for item in evidence],
        "safety": _draft_safety(),
    }
    approval.decision_json = None
    approval.decided_by_user_id = None
    approval.decided_at = None
    db.flush()
    return approval


def _email_approval(db: Session, project_id: int, supplier_id: int) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.project_id == project_id,
            ApprovalRequest.supplier_id == supplier_id,
            ApprovalRequest.request_type == "send_email",
        )
        .order_by(ApprovalRequest.id)
    )


def _upsert_missing_info_prompt(
    db: Session,
    project_id: int,
    missing: list[str],
    supplier_name: str,
) -> ChatMessage | None:
    if not missing:
        return None
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project_id).order_by(Conversation.id))
    if conversation is None:
        return None
    content = (
        f"Before I can safely send the draft to {supplier_name}, please provide: "
        f"{', '.join(missing)}."
    )
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.sender == "assistant",
            ChatMessage.message_type == "missing_info_prompt",
            ChatMessage.content == content,
        )
    )
    if existing is not None:
        return existing
    message = ChatMessage(
        conversation_id=conversation.id,
        sender="assistant",
        message_type="missing_info_prompt",
        content=content,
        metadata_json={"missing_business_info": missing, "supplier_name": supplier_name, "source": "email_draft_workflow"},
    )
    db.add(message)
    db.flush()
    return message


def _draft_safety() -> dict[str, Any]:
    return {
        "requires_user_approval": True,
        "sends_outreach": False,
        "performs_browser_submission": False,
        "uses_only_known_business_facts": True,
    }
