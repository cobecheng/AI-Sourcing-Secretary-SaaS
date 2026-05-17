from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AgentRun
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


def create_project(client: TestClient) -> int:
    response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG suppliers in the UK."},
    )
    return response.json()["project_id"]


def test_llm_models_returns_default_task_routing_table() -> None:
    client = TestClient(app)

    response = client.get("/llm/models")

    assert response.status_code == 200
    payload = response.json()
    routes = {item["task_type"]: item for item in payload}
    assert routes["milestone_update"]["tier"] == 0
    assert routes["supplier_relevance_scoring"]["tier"] == 2
    assert routes["supplier_trust_scoring"]["fallback_tier"] == 3
    assert routes["final_report_generation"]["model"] == "mock-premium"


def test_llm_complete_uses_internal_router_defaults_and_logs_schema_version() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(client)

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "supplier_relevance_scoring",
                "prompt": "Score supplier relevance.",
                "estimated_cost_usd": 0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["routing"]["tier"] == 2
        assert payload["routing"]["provider"] == "mock"
        assert payload["routing"]["model"] == "mock-mid"
        assert payload["routing"]["schema_version"] == "mock-v1"
        assert payload["routing"]["decision"] == "accept"
        assert payload["agent_run"]["provider"] == "mock"
        assert payload["agent_run"]["model"] == "mock-mid"
        assert payload["agent_run"]["schema_version"] == "mock-v1"

        with session_factory() as db:
            run = db.scalars(select(AgentRun)).one()

        assert run.agent_type == "llm_router"
        assert run.prompt_version == "supplier_relevance_scoring:mock-v1"
        assert run.schema_version == "mock-v1"
        assert run.output_json["routing_decision"] == "accept"


def test_low_confidence_task_uses_fallback_path() -> None:
    with make_test_client() as (client, _session_factory):
        project_id = create_project(client)

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "supplier_trust_scoring",
                "prompt": "Score supplier trust.",
                "confidence": 0.55,
                "estimated_cost_usd": 0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["routing"]["decision"] == "escalate_low_confidence"
        assert payload["routing"]["fallback_used"] is True
        assert payload["routing"]["tier"] == 3
        assert payload["routing"]["model"] == "mock-premium"
        assert payload["agent_run"]["fallback_used"] is True


def test_risky_task_escalates_to_user_without_provider_sdk() -> None:
    with make_test_client() as (client, _session_factory):
        project_id = create_project(client)

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "browser_action_decision",
                "prompt": "Decide whether to bypass login and submit payment terms.",
                "estimated_cost_usd": 0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["requires_user_approval"] is True
        assert payload["routing"]["decision"] == "escalate_to_user"
        assert "risky terms" in payload["routing"]["reason"]
        assert payload["agent_run"]["status"] == "needs_user_approval"


def test_schema_validation_failure_is_represented_in_routing() -> None:
    with make_test_client() as (client, _session_factory):
        project_id = create_project(client)

        response = client.post(
            "/llm/complete",
            json={
                "project_id": project_id,
                "task_type": "supplier_website_extraction",
                "prompt": "Extract supplier data.",
                "input_json": {"supplier_name": "CardTrade"},
                "required_output_fields": ["supplier_name", "website"],
                "estimated_cost_usd": 0,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["routing"]["decision"] == "schema_validation_failed"
        assert payload["routing"]["confidence"] < 0.6
        assert "website" in payload["routing"]["reason"]
