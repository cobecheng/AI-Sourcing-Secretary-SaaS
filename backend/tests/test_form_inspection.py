from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, ContactForm, FormSubmission, ProjectMemory, Supplier
from app.db.session import get_db
from app.main import app


@contextmanager
def make_test_client() -> Generator[tuple[TestClient, sessionmaker[Session]], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), testing_session
    finally:
        app.dependency_overrides.clear()


def create_mock_project(client: TestClient) -> tuple[int, int]:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    client.post(f"/projects/{project_id}/research/start")
    return project_id, create_response.json()["conversation_id"]


def test_form_inspection_extracts_required_fields_and_asks_missing_info() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project(client)
        with session_factory() as db:
            supplier = db.scalar(select(Supplier).where(Supplier.contact_method == "contact_form"))
            supplier_id = supplier.id

        response = client.post(
            f"/suppliers/{supplier_id}/forms/inspect",
            json={
                "form_url": "https://supplier.example/wholesale",
                "page_text": (
                    "Wholesale inquiry. Required fields: business name, contact name, business email, country, "
                    "expected monthly order size. Optional fields: store website, message."
                ),
            },
        )

        assert response.status_code == 200
        payload = response.json()
        form = payload["forms"][0]
        assert payload["paused_for_review"] is False
        assert payload["chat_message_id"] is not None
        assert form["status"] == "inspected"
        assert form["requires_captcha"] is False
        assert {field["name"] for field in form["fields"]} >= {
            "business_name",
            "contact_name",
            "business_email",
            "country",
            "monthly_order_size",
        }
        assert "business_email" in form["required_missing_fields"]

        with session_factory() as db:
            messages = db.scalars(select(ChatMessage).where(ChatMessage.message_type == "missing_info_prompt")).all()
            submissions = db.scalars(select(FormSubmission)).all()

        assert any("business_email" in message.content for message in messages)
        assert submissions == []


def test_form_inspection_maps_existing_project_memory_values() -> None:
    with make_test_client() as (client, session_factory):
        project_id, _conversation_id = create_mock_project(client)
        with session_factory() as db:
            supplier_id = db.scalar(select(Supplier.id).where(Supplier.contact_method == "contact_form"))
            db.add(
                ProjectMemory(
                    project_id=project_id,
                    key="provided_business_info",
                    value={
                        "business_name": "Card Shop Ltd",
                        "contact_name": "Cobe",
                        "business_email": "owner@example.test",
                        "country": "UK",
                        "monthly_order_size": "1000",
                    },
                )
            )
            db.commit()

        response = client.post(
            f"/suppliers/{supplier_id}/forms/inspect",
            json={
                "page_text": "Required fields: business name, contact name, business email, country, monthly order size."
            },
        )

        assert response.status_code == 200
        form = response.json()["forms"][0]
        assert form["required_missing_fields"] == []
        assert response.json()["chat_message_id"] is None
        assert all(field["has_value"] for field in form["fields"] if field["required"])


def test_form_inspection_pauses_for_captcha_login_payment_and_document_cases() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project(client)
        with session_factory() as db:
            supplier_id = db.scalar(select(Supplier.id).where(Supplier.contact_method == "contact_form"))

        response = client.post(
            f"/suppliers/{supplier_id}/forms/inspect",
            json={
                "page_text": (
                    "Wholesale application. Required fields: business email. CAPTCHA required. "
                    "Please login before document upload and payment setup."
                )
            },
        )

        assert response.status_code == 200
        payload = response.json()
        form = payload["forms"][0]
        assert payload["paused_for_review"] is True
        assert form["status"] == "paused_for_review"
        assert form["requires_captcha"] is True
        assert form["requires_login"] is True
        assert {"captcha", "login", "payment", "document_upload"}.issubset(set(form["safety_flags"]))
        assert payload["chat_message_id"] is not None


def test_inspected_forms_can_be_listed() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project(client)
        with session_factory() as db:
            supplier_id = db.scalar(select(Supplier.id).where(Supplier.contact_method == "contact_form"))

        client.post(f"/suppliers/{supplier_id}/forms/inspect", json={"page_text": "Required fields: email, message."})
        response = client.get(f"/suppliers/{supplier_id}/forms")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["supplier_id"] == supplier_id
        assert payload[0]["fields"]


def test_form_inspection_requires_existing_supplier() -> None:
    with make_test_client() as (client, _session_factory):
        response = client.post("/suppliers/999/forms/inspect", json={"page_text": "Required fields: email."})

        assert response.status_code == 404
