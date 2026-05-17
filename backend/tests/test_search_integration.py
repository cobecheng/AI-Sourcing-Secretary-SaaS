from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.models import Project, ProjectMemory, User
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
        get_settings.cache_clear()


def create_project(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        user = User(email="search-owner@example.test", name="Search Owner")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="Search test", status="mock_research")
        db.add(project)
        db.commit()
        return project.id


def test_mock_search_returns_cached_records_with_query_context_without_api_keys() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)

        response = client.post(
            f"/projects/{project_id}/research/search",
            json={"query": "Pokemon TCG wholesale UK", "limit": 2},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "mock_search"
        assert payload["mock_mode"] is True
        assert payload["cache_status"] == "stored"
        assert payload["fallback_reason"] == "mock_mode_or_real_search_disabled"
        assert len(payload["results"]) == 2
        assert all(result["source_url"].startswith("https://example.test") for result in payload["results"])
        assert all(result["title"] for result in payload["results"])
        assert all(result["snippet"] for result in payload["results"])
        assert {result["query"] for result in payload["results"]} == {"Pokemon TCG wholesale UK"}
        assert payload["safety"]["scrapes_pages"] is False
        assert payload["safety"]["sends_outreach"] is False

        with session_factory() as db:
            memory = db.scalars(select(ProjectMemory)).all()
        assert len(memory) == 1
        assert memory[0].key.startswith("search_results:")
        assert memory[0].value["query"] == "Pokemon TCG wholesale UK"
        assert memory[0].value["results"][0]["snippet"]


def test_search_uses_cache_for_same_query_and_limit() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)

        first_response = client.post(
            f"/projects/{project_id}/research/search",
            json={"query": "Pokemon TCG wholesale UK", "limit": 2},
        )
        second_response = client.post(
            f"/projects/{project_id}/research/search",
            json={"query": "Pokemon TCG wholesale UK", "limit": 2},
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["cache_status"] == "hit"

        with session_factory() as db:
            assert len(db.scalars(select(ProjectMemory)).all()) == 1


def test_real_search_missing_exa_key_falls_back_to_mock(monkeypatch) -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)
        monkeypatch.setenv("MOCK_MODE", "false")
        monkeypatch.setenv("ENABLE_REAL_SEARCH", "true")
        monkeypatch.setenv("EXA_API_KEY", "")
        get_settings.cache_clear()

        response = client.post(
            f"/projects/{project_id}/research/search",
            json={"query": "Pokemon distributor EU", "limit": 3},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "mock_search"
        assert payload["mock_mode"] is True
        assert payload["fallback_reason"] == "missing_exa_api_key"
        assert payload["safety"]["real_search_enabled"] is False


def test_search_rejects_unknown_project() -> None:
    with make_test_client() as (client, _session_factory):
        response = client.post(
            "/projects/999/research/search",
            json={"query": "Pokemon distributor EU"},
        )

        assert response.status_code == 404
