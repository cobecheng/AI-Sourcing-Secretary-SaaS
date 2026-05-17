from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, EmailThread, ProjectMemory, SupplierTerm
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


def create_project_with_mock_research(client: TestClient) -> int:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    return project_id


def test_gmail_sync_is_explicit_mock_safe_and_idempotent() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)

        missing_body_response = client.post("/inbox/sync")
        first_response = client.post("/inbox/sync", json={"project_id": project_id})
        second_response = client.post("/inbox/sync", json={"project_id": project_id})

        assert missing_body_response.status_code == 422
        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert first_response.json()["provider"] == "mock_gmail"
        assert first_response.json()["safety"]["explicit_sync_required"] is True
        assert first_response.json()["safety"]["sends_outreach"] is False
        assert first_response.json()["synced_replies"] == 1
        assert second_response.json()["synced_replies"] == 0
        assert second_response.json()["cache_status"] == "hit"

        with session_factory() as db:
            assert len(db.scalars(select(EmailThread)).all()) == 1
            assert len(db.scalars(select(ChatMessage).where(ChatMessage.message_type == "supplier_reply")).all()) == 1


def test_replies_are_linked_to_suppliers_and_email_threads() -> None:
    with make_test_client() as (client, _session_factory):
        project_id = create_project_with_mock_research(client)
        sync_response = client.post("/inbox/sync", json={"project_id": project_id})

        list_response = client.get(f"/projects/{project_id}/replies")

        assert list_response.status_code == 200
        replies = list_response.json()
        assert len(replies) == 1
        assert replies[0]["reply_id"] == sync_response.json()["replies"][0]["reply_id"]
        assert replies[0]["supplier_name"] == "CardTrade Wholesale UK"
        assert replies[0]["gmail_thread_id"].startswith("mock-gmail-thread:")
        assert "business name" in replies[0]["missing_or_ambiguous_requests"]


def test_reply_term_extraction_cites_source_message_and_prompts_for_ambiguity() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        sync_response = client.post("/inbox/sync", json={"project_id": project_id})
        reply_id = sync_response.json()["replies"][0]["reply_id"]

        response = client.post(f"/replies/{reply_id}/extract")

        assert response.status_code == 200
        payload = response.json()
        assert payload["reply_id"] == reply_id
        assert payload["moq"] == "one sealed case per SKU"
        assert payload["price_list_available"] is True
        assert payload["payment_terms"] == "Pro forma before dispatch"
        assert payload["shipping_regions"] == {"regions": ["UK"]}
        assert payload["lead_time"] == "3-5 business days"
        assert "business name" in payload["missing_or_ambiguous_requests"]
        assert payload["chat_message_id"] is not None
        assert payload["safety"]["requires_followup_approval_for_replies"] is True

        with session_factory() as db:
            term = db.get(SupplierTerm, payload["supplier_term_id"])
            prompt = db.get(ChatMessage, payload["chat_message_id"])

        assert term.extracted_from_message_id == reply_id
        assert "store website" in term.account_requirements
        assert prompt.metadata_json["source"] == "reply_parsing"


def test_reply_term_extraction_is_idempotent() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        sync_response = client.post("/inbox/sync", json={"project_id": project_id})
        reply_id = sync_response.json()["replies"][0]["reply_id"]

        first_response = client.post(f"/replies/{reply_id}/extract")
        second_response = client.post(f"/replies/{reply_id}/extract")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["supplier_term_id"] == first_response.json()["supplier_term_id"]
        assert second_response.json()["chat_message_id"] == first_response.json()["chat_message_id"]
        with session_factory() as db:
            assert len(db.scalars(select(SupplierTerm)).all()) == 1
            prompts = db.scalars(
                select(ChatMessage).where(
                    ChatMessage.message_type == "missing_info_prompt",
                    ChatMessage.metadata_json["source"].as_string() == "reply_parsing",
                )
            ).all()
        assert len(prompts) == 1


def test_sync_stores_reply_memory_for_followup_drafting() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        sync_response = client.post("/inbox/sync", json={"project_id": project_id})
        thread_id = sync_response.json()["replies"][0]["email_thread_id"]

        with session_factory() as db:
            memory = db.scalar(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == f"supplier_reply:{thread_id}")
            )

        assert memory.value["reply_text"].startswith("Thanks for your inquiry")
