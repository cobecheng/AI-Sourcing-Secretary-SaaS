from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessage, Milestone, ProjectMemory
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


def test_create_project_from_chat_stores_project_conversation_messages_and_milestones() -> None:
    with make_test_client() as (client, session_factory):
        response = client.post(
            "/projects/from-chat",
            json={
                "message": "Find Pokemon TCG distributors in the UK or EU. I want booster boxes and ETBs. Prefer suppliers that accept small retailers.",
                "user_email": "owner@example.test",
                "user_name": "Shop Owner",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_name"] == "Pokemon TCG sourcing"
        assert payload["status"] == "mock_research"
        assert "store website" in payload["missing_business_info"]
        assert len(payload["created_message_ids"]) == 3

        with session_factory() as db:
            messages = db.scalars(select(ChatMessage).order_by(ChatMessage.id)).all()
            milestones = db.scalars(select(Milestone).order_by(Milestone.id)).all()
            memory = db.scalars(select(ProjectMemory).order_by(ProjectMemory.id)).all()

        assert [message.message_type for message in messages] == [
            "text",
            "milestone_update",
            "missing_info_prompt",
        ]
        assert milestones[0].name == "request_understood"
        assert milestones[0].status == "complete"
        assert {item.key for item in memory} == {
            "original_sourcing_request",
            "structured_sourcing_request",
            "missing_business_info",
        }


def test_created_project_messages_can_be_listed() -> None:
    with make_test_client() as (client, _session_factory):
        create_response = client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG suppliers in the UK."},
        )
        project_id = create_response.json()["project_id"]

        response = client.get(f"/projects/{project_id}/messages")

        assert response.status_code == 200
        payload = response.json()
        assert payload["project_id"] == project_id
        assert len(payload["messages"]) == 3
        assert payload["messages"][2]["message_type"] == "missing_info_prompt"


def test_project_list_includes_created_mock_project() -> None:
    with make_test_client() as (client, _session_factory):
        client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG distributors in the UK or EU."},
        )

        response = client.get("/projects")

        assert response.status_code == 200
        assert response.json()[0]["name"] == "Pokemon TCG sourcing"
        assert response.json()[0]["supplier_count"] == 0
