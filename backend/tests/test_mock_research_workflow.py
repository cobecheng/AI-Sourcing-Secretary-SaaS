from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ApprovalRequest, ContactForm, OutreachMessage, Supplier, SupplierSource
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


def test_mock_research_workflow_creates_suppliers_milestones_and_pending_approvals() -> None:
    with make_test_client() as (client, session_factory):
        create_response = client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG distributors in the UK or EU for booster boxes and ETBs."},
        )
        project_id = create_response.json()["project_id"]

        response = client.post(f"/projects/{project_id}/research/start")

        assert response.status_code == 200
        payload = response.json()
        assert payload["mock_mode"] is True
        assert payload["workflow"]["status"] == "waiting_for_approval"
        assert payload["project_status"] == "mock_research_ready_for_approval"
        assert {supplier["contact_method"] for supplier in payload["suppliers"]} == {
            "email",
            "contact_form",
            "manual_review",
        }
        assert all(supplier["evidence"] for supplier in payload["suppliers"])
        assert all(supplier["trust_score"] is not None for supplier in payload["suppliers"])
        assert all(supplier["relevance_score"] is not None for supplier in payload["suppliers"])
        assert {approval["request_type"] for approval in payload["approvals"]} == {
            "send_email",
            "submit_contact_form",
        }
        assert all(approval["status"] == "pending" for approval in payload["approvals"])
        assert all(approval["payload_json"]["outbound_actions_performed"] == 0 for approval in payload["approvals"])

        milestone_statuses = {milestone["name"]: milestone["status"] for milestone in payload["milestones"]}
        assert milestone_statuses["suppliers_discovered"] == "complete"
        assert milestone_statuses["suppliers_verified"] == "complete"
        assert milestone_statuses["outreach_approval"] == "pending_user"

        with session_factory() as db:
            suppliers = db.scalars(select(Supplier)).all()
            sources = db.scalars(select(SupplierSource)).all()
            forms = db.scalars(select(ContactForm)).all()
            outreach = db.scalars(select(OutreachMessage)).all()
            approvals = db.scalars(select(ApprovalRequest)).all()

        assert len(suppliers) == 3
        assert len(sources) == 3
        assert len(forms) == 1
        assert len(outreach) == 1
        assert outreach[0].status == "pending_approval"
        assert outreach[0].approved_by_user is False
        assert outreach[0].sent_at is None
        assert len(approvals) == 2
        assert {approval.status for approval in approvals} == {"pending"}
        assert {approval.decided_at for approval in approvals} == {None}


def test_mock_research_status_returns_existing_workflow() -> None:
    with make_test_client() as (client, _session_factory):
        create_response = client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG suppliers in the UK."},
        )
        project_id = create_response.json()["project_id"]
        client.post(f"/projects/{project_id}/research/start")

        response = client.get(f"/projects/{project_id}/research/status")

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == project_id
        assert payload["workflow"]["workflow_name"] == "mock_sourcing_workflow"
        assert len(payload["suppliers"]) == 3
        assert len(payload["approvals"]) == 2


def test_mock_research_start_is_idempotent() -> None:
    with make_test_client() as (client, session_factory):
        create_response = client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG suppliers in the UK."},
        )
        project_id = create_response.json()["project_id"]

        first_response = client.post(f"/projects/{project_id}/research/start")
        second_response = client.post(f"/projects/{project_id}/research/start")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert len(second_response.json()["suppliers"]) == 3
        assert len(second_response.json()["approvals"]) == 2

        with session_factory() as db:
            assert len(db.scalars(select(Supplier)).all()) == 3
            assert len(db.scalars(select(SupplierSource)).all()) == 3
            assert len(db.scalars(select(ApprovalRequest)).all()) == 2
            assert len(db.scalars(select(OutreachMessage)).all()) == 1


def test_mock_research_requires_existing_project() -> None:
    with make_test_client() as (client, _session_factory):
        response = client.post("/projects/999/research/start")

        assert response.status_code == 404
