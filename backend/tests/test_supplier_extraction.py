from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import Project, ProjectMemory, Supplier, SupplierSource, User
from app.db.session import get_db
from app.main import app
from app.services.supplier_extraction import normalized_domain, normalize_supplier_url


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


def create_project(session_factory: sessionmaker[Session]) -> int:
    with session_factory() as db:
        user = User(email="supplier-owner@example.test", name="Supplier Owner")
        db.add(user)
        db.flush()
        project = Project(user_id=user.id, name="Supplier extraction", status="mock_research")
        db.add(project)
        db.commit()
        return project.id


def search_result(url: str, title: str, snippet: str, rank: int = 1) -> dict[str, object]:
    return {
        "source_url": url,
        "title": title,
        "snippet": snippet,
        "query": "Pokemon TCG wholesale UK",
        "provider": "mock_search",
        "rank": rank,
    }


def test_url_normalization_and_domain_deduplication_are_deterministic() -> None:
    assert normalize_supplier_url("HTTPS://www.Example.Test/path/?utm=1#section") == "https://example.test/path"
    assert normalized_domain("www.Example.Test/path") == "example.test"

    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)
        response = client.post(
            f"/projects/{project_id}/suppliers/extract",
            json={
                "results": [
                    search_result(
                        "https://www.CardTrade-Wholesale.example/pokemon?utm=1",
                        "CardTrade Wholesale UK Pokemon sealed products",
                        "Wholesale Pokemon booster boxes and ETBs for trade accounts.",
                        1,
                    ),
                    search_result(
                        "https://cardtrade-wholesale.example/contact",
                        "CardTrade Wholesale contact",
                        "Distributor contact form for Pokemon TCG wholesale inquiries.",
                        2,
                    ),
                ]
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["candidates_seen"] == 2
        assert payload["duplicates_merged"] == 1
        assert len(payload["suppliers"]) == 1
        supplier = payload["suppliers"][0]
        assert supplier["website"] == "https://cardtrade-wholesale.example"
        assert supplier["scoring_metadata"]["normalized_domain"] == "cardtrade-wholesale.example"
        assert len(supplier["scoring_metadata"]["evidence_urls"]) == 2

        with session_factory() as db:
            assert len(db.scalars(select(Supplier)).all()) == 1
            assert len(db.scalars(select(SupplierSource)).all()) == 2


def test_supplier_fields_are_validated_and_scores_retain_evidence_metadata() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)

        response = client.post(
            f"/projects/{project_id}/suppliers/extract",
            json={
                "results": [
                    search_result(
                        "https://eu-tcg-distribution.example/contact",
                        "EU TCG Distribution wholesale inquiry",
                        "Distributor contact form for EU retailers seeking sealed TCG products.",
                    )
                ]
            },
        )

        assert response.status_code == 200
        supplier = response.json()["suppliers"][0]
        assert supplier["name"] == "EU TCG Distribution"
        assert supplier["supplier_type"] == "Distributor"
        assert supplier["contact_method"] == "contact_form"
        assert supplier["relevance_score"] > 0
        assert supplier["trust_score"] > 0
        assert supplier["evidence"][0]["url"] == "https://eu-tcg-distribution.example/contact"
        assert supplier["scoring_metadata"]["confidence"] >= 0.6
        assert supplier["scoring_metadata"]["routing_decision"] in {"accept", "verify_with_fallback"}
        assert supplier["scoring_metadata"]["evidence_urls"] == ["https://eu-tcg-distribution.example/contact"]

        with session_factory() as db:
            score_memory = db.scalar(select(ProjectMemory).where(ProjectMemory.key.like("supplier_score:%")))
        assert score_memory.value["normalized_domain"] == "eu-tcg-distribution.example"
        assert score_memory.value["evidence_urls"] == ["https://eu-tcg-distribution.example/contact"]


def test_low_confidence_supplier_becomes_manual_review_needed() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)

        response = client.post(
            f"/projects/{project_id}/suppliers/extract",
            json={
                "results": [
                    search_result(
                        "https://unclear-example.test/about",
                        "About us",
                        "General company page with no clear sourcing evidence.",
                    )
                ]
            },
        )

        assert response.status_code == 200
        supplier = response.json()["suppliers"][0]
        assert supplier["status"] == "Manual Review Needed"
        assert supplier["scoring_metadata"]["confidence"] < 0.6
        assert supplier["scoring_metadata"]["routing_decision"] == "escalate_low_confidence"


def test_extraction_can_use_latest_cached_search_results_and_list_suppliers() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)
        search_response = client.post(
            f"/projects/{project_id}/research/search",
            json={"query": "Pokemon TCG wholesale UK", "limit": 2},
        )
        assert search_response.status_code == 200

        extract_response = client.post(f"/projects/{project_id}/suppliers/extract")
        list_response = client.get(f"/projects/{project_id}/suppliers")
        supplier_id = extract_response.json()["suppliers"][0]["id"]
        detail_response = client.get(f"/suppliers/{supplier_id}")

        assert extract_response.status_code == 200
        assert extract_response.json()["candidates_seen"] == 2
        assert extract_response.json()["duplicates_merged"] == 1
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1
        assert detail_response.status_code == 200
        assert detail_response.json()["id"] == supplier_id


def test_extraction_rejects_invalid_supplier_url_schema() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project(session_factory)

        response = client.post(
            f"/projects/{project_id}/suppliers/extract",
            json={
                "results": [
                    search_result(
                        "not a url",
                        "Broken Supplier",
                        "Wholesale Pokemon distributor.",
                    )
                ]
            },
        )

        assert response.status_code == 422
