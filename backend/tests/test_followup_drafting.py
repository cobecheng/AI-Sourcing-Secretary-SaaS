from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ApprovalRequest, ChatMessage, EmailThread, OutreachMessage, ProjectMemory, Supplier
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


def create_project_supplier_and_thread(client: TestClient, session_factory: sessionmaker[Session]) -> tuple[int, int, int]:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    with session_factory() as db:
        supplier = db.scalar(select(Supplier).where(Supplier.contact_method == "email"))
        thread = EmailThread(supplier_id=supplier.id, gmail_thread_id=f"mock-thread-{supplier.id}", status="open")
        db.add(thread)
        db.commit()
        return project_id, supplier.id, thread.id


def test_followup_draft_uses_only_known_business_facts_and_creates_approval() -> None:
    with make_test_client() as (client, session_factory):
        project_id, _supplier_id, thread_id = create_project_supplier_and_thread(client, session_factory)
        business_info = {
            "business_name": "CardEdge Collectibles",
            "contact_name": "Cobe Cheng",
            "business_email": "buyer@cardedge.example",
            "store_website": "https://cardedge.example",
            "country": "United Kingdom",
            "monthly_order_size": "20 booster boxes",
        }
        with session_factory() as db:
            db.add(ProjectMemory(project_id=project_id, key="provided_business_info", value=business_info))
            db.commit()

        response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Please send your business details and monthly order volume."},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "pending_approval"
        assert payload["missing_business_info"] == []
        assert payload["blocked_commitments"] == []
        assert payload["outbound_performed"] is False
        assert payload["safety"]["sends_outreach"] is False
        for value in business_info.values():
            assert value in payload["body"]
        assert "payment terms" not in payload["body"].lower()
        assert "exclusive" not in payload["body"].lower()

        with session_factory() as db:
            approval = db.get(ApprovalRequest, payload["approval_request_id"])
            outreach = db.get(OutreachMessage, payload["outreach_id"])

        assert approval.request_type == "send_followup_email"
        assert approval.status == "pending"
        assert approval.payload_json["body"] == payload["body"]
        assert approval.payload_json["outbound_actions_performed"] == 0
        assert outreach.sent_at is None


def test_missing_followup_information_becomes_chat_prompt() -> None:
    with make_test_client() as (client, session_factory):
        _project_id, _supplier_id, thread_id = create_project_supplier_and_thread(client, session_factory)

        response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Please send business name, contact name, website, country, and monthly order size."},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "business name" in payload["missing_business_info"]
        assert payload["chat_message_id"] is not None
        with session_factory() as db:
            message = db.get(ChatMessage, payload["chat_message_id"])

        assert message.message_type == "missing_info_prompt"
        assert message.metadata_json["source"] == "followup_drafting"
        assert "business name" in message.content


def test_risky_supplier_request_is_not_committed_autonomously() -> None:
    with make_test_client() as (client, session_factory):
        _project_id, _supplier_id, thread_id = create_project_supplier_and_thread(client, session_factory)

        response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Can you agree to exclusivity, contract terms, and payment terms?"},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["blocked_commitments"] == ["contract terms", "exclusivity", "payment terms"]
        assert "I cannot confirm legal, payment, contract, or exclusivity commitments" in payload["body"]
        assert payload["safety"]["blocks_legal_payment_contract_exclusivity_commitments"] is True
        with session_factory() as db:
            approval = db.get(ApprovalRequest, payload["approval_request_id"])
        assert approval.payload_json["blocked_commitments"] == payload["blocked_commitments"]


def test_followup_send_requires_approved_approval_request() -> None:
    with make_test_client() as (client, session_factory):
        _project_id, _supplier_id, thread_id = create_project_supplier_and_thread(client, session_factory)
        draft_response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Please send your business details."},
        )
        outreach_id = draft_response.json()["outreach_id"]
        approval_id = draft_response.json()["approval_request_id"]

        blocked_response = client.post(f"/outreach/{outreach_id}/approve-send")
        approve_response = client.post(f"/approvals/{approval_id}/approve", json={"user_id": 1})
        send_response = client.post(f"/outreach/{outreach_id}/approve-send")

        assert blocked_response.status_code == 403
        assert approve_response.status_code == 200
        assert send_response.status_code == 200
        assert send_response.json()["approval_request_id"] == approval_id
        assert send_response.json()["status"] == "sent_mock"
        assert send_response.json()["outbound_performed"] is False


def test_followup_draft_is_idempotent_for_thread() -> None:
    with make_test_client() as (client, session_factory):
        _project_id, _supplier_id, thread_id = create_project_supplier_and_thread(client, session_factory)

        first_response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Please send your business details."},
        )
        second_response = client.post(
            f"/replies/{thread_id}/draft-followup",
            json={"reply_text": "Please send your business details."},
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["outreach_id"] == first_response.json()["outreach_id"]
        assert second_response.json()["approval_request_id"] == first_response.json()["approval_request_id"]
        with session_factory() as db:
            assert len(db.scalars(select(OutreachMessage).where(OutreachMessage.idempotency_key == f"followup-draft:{thread_id}")).all()) == 1
            assert len(db.scalars(select(ApprovalRequest).where(ApprovalRequest.request_type == "send_followup_email")).all()) == 1
