from typing import Any
from urllib.parse import urljoin

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ChatMessage, ContactForm, Conversation, ProjectMemory, Supplier, SupplierSource
from app.schemas.forms import (
    ContactFormFieldResponse,
    ContactFormResponse,
    InspectSupplierFormsResponse,
)


FIELD_ALIASES = {
    "business_name": ["business name", "company", "company name", "store name"],
    "contact_name": ["contact name", "name", "full name"],
    "business_email": ["business email", "email", "email address"],
    "store_website": ["store website", "website", "web site"],
    "country": ["country", "region"],
    "monthly_order_size": ["monthly order", "order size", "expected monthly"],
    "message": ["message", "comments", "enquiry", "inquiry"],
}
KNOWN_MEMORY_FIELDS = {
    "business_name",
    "contact_name",
    "business_email",
    "store_website",
    "country",
    "monthly_order_size",
}
SAFETY_TERMS = {
    "captcha": "captcha",
    "log in": "login",
    "login": "login",
    "sign in": "login",
    "upload document": "document_upload",
    "document upload": "document_upload",
    "payment": "payment",
    "credit card": "payment",
    "create account": "account_creation",
    "register account": "account_creation",
    "legal": "legal_commitment",
    "contract": "legal_commitment",
}


def inspect_supplier_forms(
    db: Session,
    supplier_id: int,
    form_url: str | None = None,
    page_text: str | None = None,
) -> InspectSupplierFormsResponse:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")

    text = page_text or _best_source_text(db, supplier) or _default_mock_form_text(supplier)
    resolved_form_url = form_url or _default_form_url(supplier)
    fields = _extract_fields(text)
    safety_flags = _safety_flags(text)
    required_missing = _missing_required_fields(db, supplier.project_id, fields)
    contact_form = _upsert_contact_form(db, supplier, resolved_form_url, fields, safety_flags, required_missing)
    chat_message_id = _ask_for_missing_info(db, supplier, required_missing, safety_flags)
    db.commit()
    db.refresh(contact_form)

    response = _form_response(contact_form)
    return InspectSupplierFormsResponse(
        supplier_id=supplier.id,
        forms=[response],
        chat_message_id=chat_message_id,
        paused_for_review=bool(safety_flags),
        mock_mode=get_settings().mock_mode,
        safety={
            "submits_forms": False,
            "uses_playwright_for_real_inspection_later": True,
            "pauses_for_captcha_login_document_payment_account_legal": True,
            "missing_user_info_asked_in_chat": chat_message_id is not None,
        },
    )


def list_contact_forms(db: Session, supplier_id: int) -> list[ContactFormResponse]:
    supplier = db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status_code=404, detail="Supplier not found")
    forms = db.scalars(select(ContactForm).where(ContactForm.supplier_id == supplier_id).order_by(ContactForm.id)).all()
    return [_form_response(form) for form in forms]


def _best_source_text(db: Session, supplier: Supplier) -> str | None:
    source = db.scalar(
        select(SupplierSource)
        .where(SupplierSource.supplier_id == supplier.id, SupplierSource.extracted_text.is_not(None))
        .order_by(SupplierSource.id.desc())
    )
    return source.extracted_text if source else None


def _default_mock_form_text(supplier: Supplier) -> str:
    return (
        f"{supplier.name} wholesale inquiry form. Required fields: business name, contact name, business email, "
        "country, expected monthly order size. Optional fields: store website, message."
    )


def _default_form_url(supplier: Supplier) -> str:
    base_url = supplier.website or "https://example.test"
    return urljoin(base_url.rstrip("/") + "/", "contact")


def _extract_fields(text: str) -> list[dict[str, Any]]:
    normalized = text.lower()
    fields: list[dict[str, Any]] = []
    required_section = _required_section(normalized)
    for key, aliases in FIELD_ALIASES.items():
        matched_alias = next((alias for alias in aliases if alias in normalized), None)
        if matched_alias is None:
            continue
        fields.append(
            {
                "name": key,
                "label": matched_alias.title(),
                "field_type": "textarea" if key == "message" else "text",
                "required": matched_alias in required_section or f"required {matched_alias}" in normalized,
                "mapped_memory_key": key if key in KNOWN_MEMORY_FIELDS else None,
            }
        )
    if not fields:
        fields = [
            {
                "name": "message",
                "label": "Message",
                "field_type": "textarea",
                "required": True,
                "mapped_memory_key": None,
            }
        ]
    return fields


def _required_section(normalized_text: str) -> str:
    marker = "required fields:"
    if marker not in normalized_text:
        return normalized_text
    section = normalized_text.split(marker, 1)[1]
    return section.split(".", 1)[0]


def _safety_flags(text: str) -> list[str]:
    normalized = text.lower()
    return sorted({flag for term, flag in SAFETY_TERMS.items() if term in normalized})


def _missing_required_fields(db: Session, project_id: int, fields: list[dict[str, Any]]) -> list[str]:
    memory = db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "provided_business_info"))
    provided = set((memory.value or {}).keys()) if memory else set()
    missing = [
        field["name"]
        for field in fields
        if field["required"] and field.get("mapped_memory_key") and field["mapped_memory_key"] not in provided
    ]
    return sorted(set(missing))


def _upsert_contact_form(
    db: Session,
    supplier: Supplier,
    form_url: str,
    fields: list[dict[str, Any]],
    safety_flags: list[str],
    required_missing: list[str],
) -> ContactForm:
    contact_form = db.scalar(select(ContactForm).where(ContactForm.supplier_id == supplier.id, ContactForm.form_url == form_url))
    if contact_form is None:
        contact_form = ContactForm(supplier_id=supplier.id, form_url=form_url)
        db.add(contact_form)

    contact_form.form_type = "wholesale_inquiry"
    contact_form.fields_json = {
        "fields": fields,
        "required": [field["name"] for field in fields if field["required"]],
        "required_missing": required_missing,
        "safety_flags": safety_flags,
    }
    contact_form.requires_captcha = "captcha" in safety_flags
    contact_form.requires_login = "login" in safety_flags
    contact_form.status = "paused_for_review" if safety_flags else "inspected"
    db.flush()
    return contact_form


def _ask_for_missing_info(
    db: Session,
    supplier: Supplier,
    required_missing: list[str],
    safety_flags: list[str],
) -> int | None:
    if not required_missing and not safety_flags:
        return None
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == supplier.project_id).order_by(Conversation.id))
    if conversation is None:
        return None

    metadata = {
        "supplier_id": supplier.id,
        "missing_business_info": required_missing,
        "safety_flags": safety_flags,
        "mock_mode": get_settings().mock_mode,
    }
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.message_type == "missing_info_prompt",
            ChatMessage.metadata_json == metadata,
        )
    )
    if existing is not None:
        return existing.id

    content_parts = []
    if required_missing:
        content_parts.append(
            "The supplier form requires missing business information: " + ", ".join(required_missing) + "."
        )
    if safety_flags:
        content_parts.append(
            "I paused form handling for review because the page includes: " + ", ".join(safety_flags) + "."
        )
    message = ChatMessage(
        conversation_id=conversation.id,
        sender="assistant",
        message_type="missing_info_prompt",
        content=" ".join(content_parts),
        metadata_json=metadata,
    )
    db.add(message)
    db.flush()
    return message.id


def _form_response(form: ContactForm) -> ContactFormResponse:
    fields_json = form.fields_json or {}
    fields = fields_json.get("fields", [])
    required_missing = fields_json.get("required_missing", [])
    safety_flags = fields_json.get("safety_flags", [])
    missing_set = set(required_missing)
    return ContactFormResponse(
        id=form.id,
        supplier_id=form.supplier_id,
        form_url=form.form_url,
        form_type=form.form_type,
        fields=[
            ContactFormFieldResponse(
                name=field["name"],
                label=field["label"],
                field_type=field["field_type"],
                required=field["required"],
                mapped_memory_key=field.get("mapped_memory_key"),
                has_value=field.get("mapped_memory_key") not in missing_set if field.get("mapped_memory_key") else False,
            )
            for field in fields
        ],
        required_missing_fields=required_missing,
        requires_captcha=form.requires_captcha,
        requires_login=form.requires_login,
        status=form.status,
        safety_flags=safety_flags,
    )
