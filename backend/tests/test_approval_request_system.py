from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ApprovalRequest, AuditLog, OutreachMessage
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


def create_mock_project_with_approvals(client: TestClient) -> int:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    return project_id


def approval_ids(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as db:
        approvals = db.scalars(select(ApprovalRequest)).all()
    return {approval.request_type: approval.id for approval in approvals}


def email_outreach_id(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        return db.scalar(select(OutreachMessage.id))


def test_project_approval_list_returns_exact_payloads_and_status_counts() -> None:
    with make_test_client() as (client, _session_factory):
        project_id = create_mock_project_with_approvals(client)

        response = client.get(f"/projects/{project_id}/approvals")

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == project_id
        assert payload["status_counts"] == {"pending": 2}
        assert len(payload["items"]) == 2
        email_approval = next(item for item in payload["items"] if item["request_type"] == "send_email")
        assert email_approval["payload_json"]["recipient"] == "trade@example.test"
        assert email_approval["payload_json"]["subject"] == "Wholesale Pokemon TCG account inquiry"
        assert email_approval["payload_json"]["outbound_actions_performed"] == 0


def test_approval_lifecycle_supports_rejected_expired_and_cancelled_states_with_audit() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_approvals(client)
        ids = approval_ids(session_factory)

        reject_response = client.post(f"/approvals/{ids['send_email']}/reject", json={"user_id": 1, "note": "Need edits"})
        expire_response = client.post(f"/approvals/{ids['submit_contact_form']}/expire", json={"note": "Too old"})

        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"
        assert expire_response.status_code == 200
        assert expire_response.json()["status"] == "expired"

        with session_factory() as db:
            rejected = db.get(ApprovalRequest, ids["send_email"])
            expired = db.get(ApprovalRequest, ids["submit_contact_form"])
            audit_actions = [item.action for item in db.scalars(select(AuditLog)).all()]

        assert rejected.decision_json["decision"] == "rejected"
        assert expired.decision_json["decision"] == "expired"
        assert "approval.rejected" in audit_actions
        assert "approval.expired" in audit_actions

        approve_rejected_response = client.post(f"/approvals/{ids['send_email']}/approve", json={"user_id": 1})
        cancel_expired_response = client.post(f"/approvals/{ids['submit_contact_form']}/cancel", json={"user_id": 1})

        assert approve_rejected_response.status_code == 409
        assert cancel_expired_response.status_code == 200
        assert cancel_expired_response.json()["status"] == "cancelled"


def test_edit_sets_edited_state_updates_exact_payload_and_blocks_send_until_approved() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_approvals(client)
        ids = approval_ids(session_factory)
        outreach_id = email_outreach_id(session_factory)
        edited_payload = {
            "action": "send_email",
            "channel": "email",
            "recipient": "trade@example.test",
            "subject": "Edited wholesale inquiry",
            "body": "Exact edited body to approve.",
            "outbound_actions_performed": 0,
        }

        edit_response = client.patch(
            f"/approvals/{ids['send_email']}/edit",
            json={"user_id": 7, "note": "Tighter wording", "payload_json": edited_payload},
        )
        send_before_approval_response = client.post(f"/outreach/{outreach_id}/approve-send")
        approve_response = client.post(f"/approvals/{ids['send_email']}/approve", json={"user_id": 7})
        send_after_approval_response = client.post(f"/outreach/{outreach_id}/approve-send")

        assert edit_response.status_code == 200
        assert edit_response.json()["status"] == "edited"
        assert edit_response.json()["payload_json"] == edited_payload
        assert send_before_approval_response.status_code == 403
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"
        assert approve_response.json()["payload_json"] == edited_payload
        assert send_after_approval_response.status_code == 200

        with session_factory() as db:
            approval = db.get(ApprovalRequest, ids["send_email"])
            audit_actions = [item.action for item in db.scalars(select(AuditLog)).all()]

        assert approval.payload_json == edited_payload
        assert "approval.edited" in audit_actions
        assert "approval.approved" in audit_actions
        assert "outreach.email_sent_mock" in audit_actions


def test_cancelled_approval_does_not_unlock_outbound_action() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_approvals(client)
        ids = approval_ids(session_factory)
        outreach_id = email_outreach_id(session_factory)

        cancel_response = client.post(f"/approvals/{ids['send_email']}/cancel", json={"user_id": 2})
        send_response = client.post(f"/outreach/{outreach_id}/approve-send")

        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "cancelled"
        assert send_response.status_code == 403
        with session_factory() as db:
            approval = db.get(ApprovalRequest, ids["send_email"])
            audit_actions = [item.action for item in db.scalars(select(AuditLog)).all()]

        assert approval.status == "cancelled"
        assert "approval.cancelled" in audit_actions


def test_approved_approval_cannot_be_rejected_expired_or_cancelled_afterward() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_approvals(client)
        ids = approval_ids(session_factory)

        approve_response = client.post(f"/approvals/{ids['send_email']}/approve", json={"user_id": 1})
        reject_response = client.post(f"/approvals/{ids['send_email']}/reject", json={"user_id": 1})
        expire_response = client.post(f"/approvals/{ids['send_email']}/expire", json={"user_id": 1})
        cancel_response = client.post(f"/approvals/{ids['send_email']}/cancel", json={"user_id": 1})

        assert approve_response.status_code == 200
        assert reject_response.status_code == 409
        assert expire_response.status_code == 409
        assert cancel_response.status_code == 409
