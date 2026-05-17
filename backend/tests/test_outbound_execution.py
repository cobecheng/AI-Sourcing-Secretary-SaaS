from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ApprovalRequest, AuditLog, ContactForm, FormSubmission, OutreachMessage
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


def create_mock_project_with_outbound_records(client: TestClient) -> int:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    return project_id


def test_email_send_requires_approved_approval_request() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_outbound_records(client)
        with session_factory() as db:
            outreach_id = db.scalar(select(OutreachMessage.id))

        response = client.post(f"/outreach/{outreach_id}/approve-send")

        assert response.status_code == 403
        assert "Approved approval_request" in response.json()["detail"]


def test_approved_email_send_is_mock_safe_idempotent_and_audited() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_outbound_records(client)
        with session_factory() as db:
            outreach_id = db.scalar(select(OutreachMessage.id))
            approval_id = db.scalar(
                select(ApprovalRequest.id).where(ApprovalRequest.request_type == "send_email")
            )

        approve_response = client.post(f"/approvals/{approval_id}/approve", json={"user_id": 1})
        first_response = client.post(f"/outreach/{outreach_id}/approve-send")
        second_response = client.post(f"/outreach/{outreach_id}/approve-send")

        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "approved"
        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["status"] == "sent_mock"
        assert first_payload["outbound_performed"] is False
        assert first_payload["idempotency_key"].startswith("mock-email-draft:")
        assert first_payload["sent_at"] is not None
        assert second_response.status_code == 200
        assert second_response.json()["status"] == "idempotent_replay"
        assert second_response.json()["idempotency_key"] == first_payload["idempotency_key"]

        with session_factory() as db:
            outreach = db.get(OutreachMessage, outreach_id)
            audit_actions = [item.action for item in db.scalars(select(AuditLog)).all()]

        assert outreach.status == "sent_mock"
        assert outreach.approved_by_user is True
        assert outreach.sent_at is not None
        assert "approval.approved" in audit_actions
        assert "outreach.email_sent_mock" in audit_actions


def test_approved_form_submission_stores_mock_screenshots_and_is_idempotent() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_outbound_records(client)
        with session_factory() as db:
            form_id = db.scalar(select(ContactForm.id))
            approval_id = db.scalar(
                select(ApprovalRequest.id).where(ApprovalRequest.request_type == "submit_contact_form")
            )

        client.post(f"/approvals/{approval_id}/approve", json={"user_id": 1})
        first_response = client.post(f"/forms/{form_id}/approve-submit")
        second_response = client.post(f"/forms/{form_id}/approve-submit")

        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["status"] == "submitted_mock"
        assert first_payload["outbound_performed"] is False
        assert first_payload["screenshot_before_url"].startswith("mock://screenshots")
        assert first_payload["screenshot_after_url"].startswith("mock://screenshots")
        assert second_response.status_code == 200
        assert second_response.json()["status"] == "idempotent_replay"
        assert second_response.json()["idempotency_key"] == first_payload["idempotency_key"]

        with session_factory() as db:
            submissions = db.scalars(select(FormSubmission)).all()
            audit_actions = [item.action for item in db.scalars(select(AuditLog)).all()]

        assert len(submissions) == 1
        assert submissions[0].approved_by_user is True
        assert submissions[0].submitted_at is not None
        assert "form.submitted_mock" in audit_actions


def test_form_submission_blocks_captcha_login_and_risky_commitments() -> None:
    with make_test_client() as (client, session_factory):
        create_mock_project_with_outbound_records(client)
        with session_factory() as db:
            form = db.scalar(select(ContactForm))
            form_id = form.id
            form.requires_captcha = True
            approval_id = db.scalar(
                select(ApprovalRequest.id).where(ApprovalRequest.request_type == "submit_contact_form")
            )
            db.commit()

        client.post(f"/approvals/{approval_id}/approve", json={"user_id": 1})
        response = client.post(f"/forms/{form_id}/approve-submit")

        assert response.status_code == 409
        assert "captcha" in response.json()["detail"]
