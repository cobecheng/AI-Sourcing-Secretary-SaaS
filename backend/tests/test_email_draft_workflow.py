from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ApprovalRequest, ChatMessage, OutreachMessage, ProjectMemory, Supplier
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
        json={"message": "Find Pokemon TCG distributors in the UK or EU for booster boxes and ETBs."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    return project_id


def email_supplier_id(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return db.scalar(select(Supplier.id).where(Supplier.contact_method == "email"))


def test_email_draft_uses_evidence_and_never_sends() -> None:
    with make_test_client() as (client, session_factory):
        create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)

        response = client.post(f"/suppliers/{supplier_id}/outreach/draft")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "pending_approval"
        assert payload["outbound_performed"] is False
        assert payload["safety"]["sends_outreach"] is False
        assert payload["missing_business_info"]
        assert payload["evidence"][0]["url"] == "https://example.test/cardtrade-wholesale/pokemon"
        assert "https://example.test/cardtrade-wholesale/pokemon" in payload["body"]

        with session_factory() as db:
            outreach = db.get(OutreachMessage, payload["outreach_id"])
            approval = db.get(ApprovalRequest, payload["approval_request_id"])

        assert outreach.approved_by_user is False
        assert outreach.sent_at is None
        assert approval.status == "pending"
        assert approval.payload_json["outbound_actions_performed"] == 0
        assert approval.payload_json["body"] == payload["body"]
        assert approval.payload_json["evidence"][0]["url"] == payload["evidence"][0]["url"]


def test_email_draft_uses_only_provided_business_facts() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)
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

        response = client.post(f"/suppliers/{supplier_id}/outreach/draft")

        assert response.status_code == 200
        payload = response.json()
        assert payload["missing_business_info"] == []
        assert payload["hallucination_flags"] == []
        for value in business_info.values():
            assert value in payload["body"]
        assert "Mock Retailer" not in payload["body"]
        assert "small retail business" not in payload["body"]


def test_email_draft_can_store_business_facts_from_request() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)

        response = client.post(
            f"/suppliers/{supplier_id}/outreach/draft",
            json={"business_info": {"business_name": "CardEdge Collectibles", "contact_name": "Cobe Cheng"}},
        )

        assert response.status_code == 200
        payload = response.json()
        assert "CardEdge Collectibles" in payload["body"]
        assert "Cobe Cheng" in payload["body"]
        assert "business name" not in payload["missing_business_info"]
        assert "contact name" not in payload["missing_business_info"]
        with session_factory() as db:
            memory = db.scalar(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "provided_business_info")
            )
        assert memory.value["business_name"] == "CardEdge Collectibles"


def test_missing_business_details_are_surfaced_as_chat_prompt() -> None:
    with make_test_client() as (client, session_factory):
        create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)

        response = client.post(f"/suppliers/{supplier_id}/outreach/draft")

        assert response.status_code == 200
        payload = response.json()
        assert payload["chat_message_id"] is not None
        with session_factory() as db:
            message = db.get(ChatMessage, payload["chat_message_id"])
        assert message.message_type == "missing_info_prompt"
        assert "business name" in message.content
        assert message.metadata_json["source"] == "email_draft_workflow"


def test_email_draft_is_idempotent_and_updates_existing_mock_records() -> None:
    with make_test_client() as (client, session_factory):
        create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)

        first_response = client.post(f"/suppliers/{supplier_id}/outreach/draft")
        second_response = client.post(f"/suppliers/{supplier_id}/outreach/draft")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["outreach_id"] == first_response.json()["outreach_id"]
        assert second_response.json()["approval_request_id"] == first_response.json()["approval_request_id"]
        with session_factory() as db:
            outreach = db.scalars(select(OutreachMessage).where(OutreachMessage.channel == "email")).all()
            approvals = db.scalars(select(ApprovalRequest).where(ApprovalRequest.request_type == "send_email")).all()
        assert len(outreach) == 1
        assert len(approvals) == 1


def test_pending_outreach_lists_email_drafts_for_project() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_mock_research(client)
        supplier_id = email_supplier_id(session_factory)
        draft_response = client.post(f"/suppliers/{supplier_id}/outreach/draft")

        response = client.get(f"/projects/{project_id}/outreach/pending")

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == project_id
        assert payload["outbound_performed"] is False
        assert len(payload["items"]) == 1
        assert payload["items"][0]["outreach_id"] == draft_response.json()["outreach_id"]
        assert payload["items"][0]["approval_request_id"] == draft_response.json()["approval_request_id"]
        assert payload["items"][0]["evidence"][0]["url"] == "https://example.test/cardtrade-wholesale/pokemon"
