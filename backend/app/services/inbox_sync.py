from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ChatMessage, Conversation, EmailThread, Project, ProjectMemory, Supplier, SupplierTerm
from app.schemas.inbox import ExtractReplyTermsResponse, InboxSyncResponse, SupplierReplyResponse


MOCK_REPLY_TEXT = (
    "Thanks for your inquiry. Please send your business name, store website, country, and expected monthly order size. "
    "Our MOQ is one sealed case per SKU. A price list is available after account approval. "
    "Payment is pro forma before dispatch. We ship within the UK with a 3-5 business day lead time."
)
AMBIGUOUS_MARKERS = {
    "business name": "business name",
    "store website": "store website",
    "country": "country",
    "monthly order size": "expected monthly order size",
}


def sync_inbox(db: Session, project_id: int) -> InboxSyncResponse:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    suppliers = db.scalars(select(Supplier).where(Supplier.project_id == project_id).order_by(Supplier.id)).all()
    replies: list[SupplierReplyResponse] = []
    created_replies = 0
    for supplier in suppliers:
        if supplier.contact_method != "email" and not supplier.email:
            continue
        thread = _upsert_thread(db, supplier)
        reply, created = _upsert_reply_message(db, project, supplier, thread, MOCK_REPLY_TEXT)
        _store_reply_memory(db, project.id, thread.id, MOCK_REPLY_TEXT)
        created_replies += 1 if created else 0
        replies.append(_reply_response(reply, supplier, thread))

    db.commit()
    return InboxSyncResponse(
        project_id=project.id,
        mock_mode=get_settings().mock_mode,
        provider="mock_gmail",
        synced_threads=len(replies),
        synced_replies=created_replies,
        cache_status="stored" if created_replies else "hit",
        replies=replies,
        safety=_safety(),
    )


def list_project_replies(db: Session, project_id: int) -> list[SupplierReplyResponse]:
    _get_project(db, project_id)
    messages = db.scalars(
        select(ChatMessage)
        .join(Conversation, ChatMessage.conversation_id == Conversation.id)
        .where(Conversation.project_id == project_id, ChatMessage.message_type == "supplier_reply")
        .order_by(ChatMessage.created_at, ChatMessage.id)
    ).all()
    replies: list[SupplierReplyResponse] = []
    for message in messages:
        metadata = message.metadata_json or {}
        supplier = db.get(Supplier, metadata.get("supplier_id"))
        thread = db.get(EmailThread, metadata.get("email_thread_id"))
        if supplier is None or thread is None:
            continue
        replies.append(_reply_response(message, supplier, thread))
    return replies


def extract_reply_terms(db: Session, reply_id: int) -> ExtractReplyTermsResponse:
    reply = db.get(ChatMessage, reply_id)
    if reply is None or reply.message_type != "supplier_reply":
        raise HTTPException(status_code=404, detail="Supplier reply not found")
    metadata = reply.metadata_json or {}
    supplier = db.get(Supplier, metadata.get("supplier_id"))
    thread = db.get(EmailThread, metadata.get("email_thread_id"))
    if supplier is None or thread is None:
        raise HTTPException(status_code=404, detail="Supplier reply is not linked to a supplier thread")

    terms_payload = _parse_terms(reply.content)
    missing = _missing_or_ambiguous_requests(reply.content)
    term = _upsert_supplier_terms(db, supplier.id, reply.id, terms_payload)
    prompt = _upsert_ambiguity_prompt(db, supplier.project_id, supplier.name, missing)
    db.commit()
    db.refresh(term)
    if prompt is not None:
        db.refresh(prompt)

    return ExtractReplyTermsResponse(
        supplier_term_id=term.id,
        reply_id=reply.id,
        email_thread_id=thread.id,
        supplier_id=supplier.id,
        moq=term.moq,
        price_list_available=term.price_list_available,
        payment_terms=term.payment_terms,
        shipping_regions=term.shipping_regions,
        lead_time=term.lead_time,
        account_requirements=term.account_requirements,
        missing_or_ambiguous_requests=missing,
        chat_message_id=prompt.id if prompt else None,
        mock_mode=get_settings().mock_mode,
        safety=_safety(),
    )


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _upsert_thread(db: Session, supplier: Supplier) -> EmailThread:
    gmail_thread_id = f"mock-gmail-thread:{supplier.project_id}:{supplier.id}"
    thread = db.scalar(select(EmailThread).where(EmailThread.gmail_thread_id == gmail_thread_id))
    if thread is None:
        thread = EmailThread(supplier_id=supplier.id, gmail_thread_id=gmail_thread_id, status="open")
        db.add(thread)
    thread.last_message_at = datetime.now(UTC)
    db.flush()
    return thread


def _upsert_reply_message(
    db: Session,
    project: Project,
    supplier: Supplier,
    thread: EmailThread,
    body: str,
) -> tuple[ChatMessage, bool]:
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project.id).order_by(Conversation.id))
    if conversation is None:
        conversation = Conversation(project_id=project.id, user_id=project.user_id)
        db.add(conversation)
        db.flush()
    gmail_message_id = f"mock-gmail-message:{thread.gmail_thread_id}:latest"
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.message_type == "supplier_reply",
            ChatMessage.content == body,
        )
    )
    if existing is not None:
        return existing, False
    message = ChatMessage(
        conversation_id=conversation.id,
        sender="supplier",
        message_type="supplier_reply",
        content=body,
        metadata_json={
            "email_thread_id": thread.id,
            "gmail_thread_id": thread.gmail_thread_id,
            "gmail_message_id": gmail_message_id,
            "supplier_id": supplier.id,
            "subject": f"Re: Supplier information for {supplier.name}",
            "received_at": datetime.now(UTC).isoformat(),
            "source": "mock_gmail_sync",
        },
    )
    db.add(message)
    db.flush()
    return message, True


def _store_reply_memory(db: Session, project_id: int, thread_id: int, reply_text: str) -> ProjectMemory:
    key = f"supplier_reply:{thread_id}"
    memory = db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == key))
    value = {"reply_text": reply_text}
    if memory is None:
        memory = ProjectMemory(project_id=project_id, key=key, value=value)
        db.add(memory)
    else:
        memory.value = value
    db.flush()
    return memory


def _reply_response(message: ChatMessage, supplier: Supplier, thread: EmailThread) -> SupplierReplyResponse:
    metadata = message.metadata_json or {}
    return SupplierReplyResponse(
        reply_id=message.id,
        email_thread_id=thread.id,
        gmail_thread_id=thread.gmail_thread_id,
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        subject=metadata.get("subject"),
        body=message.content,
        received_at=metadata.get("received_at"),
        status=thread.status,
        missing_or_ambiguous_requests=_missing_or_ambiguous_requests(message.content),
    )


def _parse_terms(text: str) -> dict[str, object]:
    normalized = text.lower()
    return {
        "moq": "one sealed case per SKU" if "one sealed case" in normalized else None,
        "price_list_available": True if "price list is available" in normalized else None,
        "payment_terms": "Pro forma before dispatch" if "pro forma" in normalized else None,
        "shipping_regions": {"regions": ["UK"]} if "within the uk" in normalized or "ship" in normalized else None,
        "lead_time": "3-5 business days" if "3-5 business day" in normalized else None,
        "account_requirements": _account_requirements(text),
    }


def _account_requirements(text: str) -> str | None:
    missing = _missing_or_ambiguous_requests(text)
    if not missing:
        return None
    return ", ".join(missing)


def _missing_or_ambiguous_requests(text: str) -> list[str]:
    normalized = text.lower()
    return [label for marker, label in AMBIGUOUS_MARKERS.items() if marker in normalized]


def _upsert_supplier_terms(
    db: Session,
    supplier_id: int,
    reply_id: int,
    terms_payload: dict[str, object],
) -> SupplierTerm:
    term = db.scalar(select(SupplierTerm).where(SupplierTerm.supplier_id == supplier_id, SupplierTerm.extracted_from_message_id == reply_id))
    if term is None:
        term = SupplierTerm(supplier_id=supplier_id, extracted_from_message_id=reply_id)
        db.add(term)
    term.moq = terms_payload["moq"]
    term.price_list_available = terms_payload["price_list_available"]
    term.payment_terms = terms_payload["payment_terms"]
    term.shipping_regions = terms_payload["shipping_regions"]
    term.lead_time = terms_payload["lead_time"]
    term.account_requirements = terms_payload["account_requirements"]
    db.flush()
    return term


def _upsert_ambiguity_prompt(
    db: Session,
    project_id: int,
    supplier_name: str,
    missing: list[str],
) -> ChatMessage | None:
    if not missing:
        return None
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project_id).order_by(Conversation.id))
    if conversation is None:
        return None
    content = f"{supplier_name} asked for missing or ambiguous details: {', '.join(missing)}."
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
        metadata_json={"source": "reply_parsing", "missing_or_ambiguous_requests": missing, "supplier_name": supplier_name},
    )
    db.add(message)
    db.flush()
    return message


def _safety() -> dict[str, object]:
    return {
        "explicit_sync_required": True,
        "idempotent": True,
        "mock_gmail_only": True,
        "sends_outreach": False,
        "requires_followup_approval_for_replies": True,
    }
