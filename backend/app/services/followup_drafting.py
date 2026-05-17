from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ApprovalRequest, ChatMessage, Conversation, EmailThread, OutreachMessage, ProjectMemory, Supplier
from app.schemas.inbox import DraftFollowupRequest, FollowupDraftResponse


BUSINESS_FIELDS: dict[str, str] = {
    "business_name": "business name",
    "contact_name": "contact name",
    "business_email": "business email",
    "store_website": "store website",
    "country": "country",
    "monthly_order_size": "expected monthly order size",
}
RISKY_COMMITMENT_TERMS = {
    "contract": "contract terms",
    "legal": "legal terms",
    "payment": "payment terms",
    "exclusivity": "exclusivity",
    "exclusive": "exclusivity",
}


def draft_followup_reply(
    db: Session,
    reply_id: int,
    request: DraftFollowupRequest | None = None,
) -> FollowupDraftResponse:
    thread = db.get(EmailThread, reply_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Email thread not found")
    supplier = db.get(Supplier, thread.supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if request and request.business_info:
        _store_business_info(db, supplier.project_id, request.business_info)
    reply_text = _reply_text(db, supplier.project_id, thread.id, request.reply_text if request else None)
    business_info = _business_info(db, supplier.project_id)
    missing = _missing_fields(reply_text, business_info)
    blocked_commitments = _blocked_commitments(reply_text)
    subject = f"Re: Supplier information for {supplier.name}"
    body = _draft_body(supplier, business_info, missing, blocked_commitments)
    outreach = _upsert_followup_outreach(db, supplier, thread, subject, body)
    approval = _upsert_followup_approval(db, supplier, thread, outreach, missing, blocked_commitments, reply_text)
    chat_message = _upsert_missing_prompt(db, supplier.project_id, supplier.name, missing, blocked_commitments)

    db.commit()
    db.refresh(outreach)
    db.refresh(approval)
    if chat_message is not None:
        db.refresh(chat_message)

    return FollowupDraftResponse(
        outreach_id=outreach.id,
        approval_request_id=approval.id,
        email_thread_id=thread.id,
        project_id=supplier.project_id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        recipient=supplier.email,
        subject=subject,
        body=body,
        status=outreach.status,
        missing_business_info=missing,
        blocked_commitments=blocked_commitments,
        chat_message_id=chat_message.id if chat_message else None,
        mock_mode=get_settings().mock_mode,
        outbound_performed=False,
        safety=_safety(),
    )


def _reply_text(db: Session, project_id: int, thread_id: int, provided_text: str | None) -> str:
    key = f"supplier_reply:{thread_id}"
    memory = db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == key))
    if provided_text:
        value = {"reply_text": provided_text}
        if memory is None:
            db.add(ProjectMemory(project_id=project_id, key=key, value=value))
        else:
            memory.value = value
        db.flush()
        return provided_text
    if memory is not None:
        return str(memory.value.get("reply_text") or "")
    return "Supplier asked for business details before sharing wholesale information."


def _business_info(db: Session, project_id: int) -> dict[str, str]:
    memory = db.scalar(
        select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "provided_business_info")
    )
    if memory is None:
        return {}
    return {str(key): str(value) for key, value in memory.value.items() if value}


def _store_business_info(db: Session, project_id: int, business_info: dict[str, str]) -> None:
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


def _missing_fields(reply_text: str, business_info: dict[str, str]) -> list[str]:
    requested_keys = set(BUSINESS_FIELDS)
    normalized = reply_text.lower()
    if "monthly" not in normalized and "volume" not in normalized and "order size" not in normalized:
        requested_keys.discard("monthly_order_size")
    return [label for key, label in BUSINESS_FIELDS.items() if key in requested_keys and not business_info.get(key)]


def _blocked_commitments(reply_text: str) -> list[str]:
    normalized = reply_text.lower()
    return sorted({label for term, label in RISKY_COMMITMENT_TERMS.items() if term in normalized})


def _draft_body(
    supplier: Supplier,
    business_info: dict[str, str],
    missing: list[str],
    blocked_commitments: list[str],
) -> str:
    lines = [
        f"Hello {supplier.name},",
        "",
        "Thanks for getting back to me. I can share the confirmed business details below.",
    ]
    for key, label in BUSINESS_FIELDS.items():
        value = business_info.get(key)
        if value:
            lines.append(f"{label.title()}: {value}")
    if missing:
        lines.extend(["", "I still need to confirm the following before sending a complete answer:"])
        lines.extend(f"- {field}" for field in missing)
    if blocked_commitments:
        lines.extend(
            [
                "",
                "I cannot confirm legal, payment, contract, or exclusivity commitments in this message.",
                "Those details need separate review and explicit approval.",
            ]
        )
    lines.extend(
        [
            "",
            "Could you share the next steps for opening a trade account once these details are complete?",
            "",
            "Best,",
            business_info.get("contact_name") or "[contact name needed]",
        ]
    )
    return "\n".join(lines)


def _upsert_followup_outreach(
    db: Session,
    supplier: Supplier,
    thread: EmailThread,
    subject: str,
    body: str,
) -> OutreachMessage:
    key = f"followup-draft:{thread.id}"
    outreach = db.scalar(select(OutreachMessage).where(OutreachMessage.idempotency_key == key))
    if outreach is None:
        outreach = OutreachMessage(
            project_id=supplier.project_id,
            supplier_id=supplier.id,
            channel="email",
            idempotency_key=key,
        )
        db.add(outreach)
    outreach.subject = subject
    outreach.body = body
    outreach.status = "pending_approval"
    outreach.approved_by_user = False
    outreach.sent_at = None
    db.flush()
    return outreach


def _upsert_followup_approval(
    db: Session,
    supplier: Supplier,
    thread: EmailThread,
    outreach: OutreachMessage,
    missing: list[str],
    blocked_commitments: list[str],
    reply_text: str,
) -> ApprovalRequest:
    approvals = db.scalars(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.project_id == supplier.project_id,
            ApprovalRequest.supplier_id == supplier.id,
            ApprovalRequest.request_type == "send_followup_email",
        )
        .order_by(ApprovalRequest.id)
    ).all()
    approval = next((item for item in approvals if (item.payload_json or {}).get("email_thread_id") == thread.id), None)
    if approval is None:
        approval = ApprovalRequest(project_id=supplier.project_id, supplier_id=supplier.id, request_type="send_followup_email")
        db.add(approval)
    approval.status = "pending"
    approval.title = f"Approve follow-up reply to {supplier.name}"
    approval.payload_json = {
        "action": "send_followup_email",
        "channel": "email",
        "email_thread_id": thread.id,
        "outreach_id": outreach.id,
        "recipient": supplier.email,
        "subject": outreach.subject,
        "body": outreach.body,
        "supplier_reply_text": reply_text,
        "missing_fields": missing,
        "blocked_commitments": blocked_commitments,
        "outbound_actions_performed": 0,
        "mock_mode": get_settings().mock_mode,
        "safety": _safety(),
    }
    approval.decision_json = None
    approval.decided_by_user_id = None
    approval.decided_at = None
    db.flush()
    return approval


def _upsert_missing_prompt(
    db: Session,
    project_id: int,
    supplier_name: str,
    missing: list[str],
    blocked_commitments: list[str],
) -> ChatMessage | None:
    if not missing and not blocked_commitments:
        return None
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project_id).order_by(Conversation.id))
    if conversation is None:
        return None
    parts = []
    if missing:
        parts.append(f"missing details: {', '.join(missing)}")
    if blocked_commitments:
        parts.append(f"review needed for: {', '.join(blocked_commitments)}")
    content = f"Before I send the follow-up to {supplier_name}, please resolve {', and '.join(parts)}."
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
        metadata_json={
            "missing_business_info": missing,
            "blocked_commitments": blocked_commitments,
            "source": "followup_drafting",
        },
    )
    db.add(message)
    db.flush()
    return message


def _safety() -> dict[str, Any]:
    return {
        "requires_user_approval": True,
        "sends_outreach": False,
        "uses_only_known_business_facts": True,
        "blocks_legal_payment_contract_exclusivity_commitments": True,
    }
