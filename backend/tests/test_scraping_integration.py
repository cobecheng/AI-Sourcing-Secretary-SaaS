from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db.base import Base
from app.db.models import Project, Supplier, SupplierSource, User
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


def create_supplier(session_factory: sessionmaker[Session], website: str | None = "https://example.test/trade") -> int:
    with session_factory() as db:
        user = User(email="scrape-owner@example.test", name="Scrape Owner")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="Scrape test", status="mock_research")
        db.add(project)
        db.flush()
        supplier = Supplier(
            project_id=project.id,
            name="Scrape Fixture Supplier",
            website=website,
            contact_method="email",
            status="Discovered",
        )
        db.add(supplier)
        db.commit()
        return supplier.id


def test_mock_scrape_stores_supplier_source_without_api_keys() -> None:
    with make_test_client() as (client, session_factory):
        supplier_id = create_supplier(session_factory)

        response = client.post(f"/suppliers/{supplier_id}/scrape")

        assert response.status_code == 200
        payload = response.json()
        assert payload["mock_mode"] is True
        assert payload["provider"] == "mock_scraper"
        assert payload["cache_status"] == "stored"
        assert payload["content_length"] > 0
        assert payload["source"]["url"] == "https://example.test/trade"
        assert payload["source"]["source_type"] == "mock_scrape_cache"
        assert "Firecrawl output" in payload["source"]["extracted_text"]
        assert payload["safety"]["submits_forms"] is False
        assert payload["safety"]["sends_outreach"] is False

        with session_factory() as db:
            sources = db.scalars(select(SupplierSource)).all()
        assert len(sources) == 1
        assert sources[0].extracted_text is not None


def test_mock_scrape_reuses_cached_supplier_source() -> None:
    with make_test_client() as (client, session_factory):
        supplier_id = create_supplier(session_factory)

        first_response = client.post(f"/suppliers/{supplier_id}/scrape")
        second_response = client.post(f"/suppliers/{supplier_id}/scrape")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["cache_status"] == "hit"
        assert second_response.json()["source"]["id"] == first_response.json()["source"]["id"]

        with session_factory() as db:
            assert len(db.scalars(select(SupplierSource)).all()) == 1


def test_supplier_sources_can_be_listed() -> None:
    with make_test_client() as (client, session_factory):
        supplier_id = create_supplier(session_factory)
        client.post(f"/suppliers/{supplier_id}/scrape", json={"url": "https://example.test/wholesale"})

        response = client.get(f"/suppliers/{supplier_id}/sources")

        assert response.status_code == 200
        payload = response.json()
        assert len(payload) == 1
        assert payload[0]["url"] == "https://example.test/wholesale"
        assert payload[0]["source_type"] == "mock_scrape_cache"


def test_real_scraping_requires_firecrawl_key(monkeypatch) -> None:
    with make_test_client() as (client, session_factory):
        supplier_id = create_supplier(session_factory)
        monkeypatch.setenv("MOCK_MODE", "false")
        monkeypatch.setenv("ENABLE_REAL_SCRAPING", "true")
        monkeypatch.setenv("FIRECRAWL_API_KEY", "")
        get_settings.cache_clear()

        response = client.post(f"/suppliers/{supplier_id}/scrape")

        assert response.status_code == 400
        assert "FIRECRAWL_API_KEY" in response.json()["detail"]


def test_scrape_rejects_non_http_urls() -> None:
    with make_test_client() as (client, session_factory):
        supplier_id = create_supplier(session_factory, website="ftp://example.test/trade")

        response = client.post(f"/suppliers/{supplier_id}/scrape")

        assert response.status_code == 400
        assert "http" in response.json()["detail"]
