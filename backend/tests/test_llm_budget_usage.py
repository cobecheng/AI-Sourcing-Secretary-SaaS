from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AgentRun, ChatMessage, LLMBudget
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


def create_project(client: TestClient) -> tuple[int, int]:
    response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG suppliers in the UK."},
    )
    payload = response.json()
    return payload["project_id"], payload["user_id"]


def test_llm_complete_logs_agent_run_and_updates_project_budget() -> None:
    with make_test_client() as (client, session_factory):
        project_id, _user_id = create_project(client)

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "milestone_update",
                "prompt": "Summarize progress.",
                "provider": "mock",
                "model": "mock-cheap",
                "input_tokens": 100,
                "output_tokens": 50,
                "estimated_cost_usd": 1,
                "actual_cost_usd": 1,
                "latency_ms": 8,
                "confidence": 0.99,
                "fallback_used": False,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["agent_run"]["task_type"] == "milestone_update"
        assert payload["agent_run"]["provider"] == "mock"
        assert payload["agent_run"]["input_tokens"] == 100
        assert payload["agent_run"]["actual_cost_usd"] == 1
        assert payload["budget"]["current_project_spend_usd"] == 1
        assert payload["requires_user_approval"] is False

        with session_factory() as db:
            runs = db.scalars(select(AgentRun)).all()
            budgets = db.scalars(select(LLMBudget)).all()

        assert len(runs) == 1
        assert runs[0].model == "mock-cheap"
        assert len(budgets) == 1
        assert float(budgets[0].current_project_spend_usd) == 1


def test_project_budget_warning_at_eighty_percent_emits_chat_message_once() -> None:
    with make_test_client() as (client, session_factory):
        project_id, _user_id = create_project(client)

        first_response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "supplier_relevance_scoring",
                "prompt": "Score suppliers.",
                "estimated_cost_usd": 4,
                "actual_cost_usd": 4,
            },
        )
        second_response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "milestone_update",
                "prompt": "Summarize progress.",
                "estimated_cost_usd": 0,
                "actual_cost_usd": 0,
            },
        )

        assert first_response.status_code == 200
        assert first_response.json()["status"] == "warning_80"
        assert first_response.json()["chat_warning_created"] is True
        assert second_response.status_code == 200
        assert second_response.json()["chat_warning_created"] is False

        with session_factory() as db:
            warnings = db.scalars(select(ChatMessage).where(ChatMessage.message_type == "budget_warning")).all()

        assert len(warnings) == 1
        assert "80 percent" in warnings[0].content


def test_budget_exceeded_pauses_expensive_task_before_logging_agent_run() -> None:
    with make_test_client() as (client, session_factory):
        project_id, _user_id = create_project(client)
        client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "milestone_update",
                "prompt": "Use most of the budget.",
                "estimated_cost_usd": 5,
                "actual_cost_usd": 5,
            },
        )

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "supplier_relevance_scoring",
                "prompt": "This should pause.",
                "estimated_cost_usd": 1,
                "actual_cost_usd": 1,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "paused_for_budget"
        assert payload["agent_run"] is None
        assert payload["requires_user_approval"] is True
        assert payload["chat_warning_created"] is True
        assert payload["budget"]["current_project_spend_usd"] == 5

        with session_factory() as db:
            runs = db.scalars(select(AgentRun)).all()
            pauses = db.scalars(select(ChatMessage).where(ChatMessage.message_type == "budget_pause")).all()

        assert len(runs) == 1
        assert len(pauses) == 1
        assert "paused this expensive model task" in pauses[0].content


def test_usage_and_budget_endpoints_return_project_and_user_totals() -> None:
    with make_test_client() as (client, _session_factory):
        project_id, user_id = create_project(client)
        client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "milestone_update",
                "prompt": "Summarize progress.",
                "input_tokens": 10,
                "output_tokens": 20,
                "estimated_cost_usd": 1.25,
                "actual_cost_usd": 1.25,
            },
        )

        project_usage = client.get(f"/llm/usage/project/{project_id}")
        user_usage = client.get(f"/llm/usage/user/{user_id}")
        project_budget = client.get(f"/llm/budgets/project/{project_id}")

        assert project_usage.status_code == 200
        assert project_usage.json()["total_actual_cost_usd"] == 1.25
        assert project_usage.json()["total_input_tokens"] == 10
        assert len(project_usage.json()["runs"]) == 1
        assert user_usage.status_code == 200
        assert user_usage.json()["total_output_tokens"] == 20
        assert project_budget.status_code == 200
        assert project_budget.json()["project_limit_usd"] == 5
