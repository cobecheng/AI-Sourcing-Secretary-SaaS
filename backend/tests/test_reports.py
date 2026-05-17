import csv
from collections.abc import Generator
from contextlib import contextmanager
from io import StringIO

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import AgentRun, ProjectMemory, Supplier, SupplierTerm
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


def create_project_with_suppliers_and_terms(client: TestClient, session_factory: sessionmaker[Session]) -> int:
    create_response = client.post(
        "/projects/from-chat",
        json={"message": "Find Pokemon TCG distributors in the UK or EU."},
    )
    project_id = create_response.json()["project_id"]
    research_response = client.post(f"/projects/{project_id}/research/start")
    assert research_response.status_code == 200
    with session_factory() as db:
        supplier = db.scalar(select(Supplier).where(Supplier.contact_method == "email"))
        db.add(
            SupplierTerm(
                supplier_id=supplier.id,
                moq="Case pack orders",
                price_list_available=True,
                payment_terms="Pro forma before dispatch",
                shipping_regions={"regions": ["UK"]},
                lead_time="3-5 business days",
                account_requirements="Retailer details and store website",
            )
        )
        db.commit()
    return project_id


def test_report_generation_cites_evidence_terms_and_uses_premium_router() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_suppliers_and_terms(client, session_factory)

        response = client.post(f"/projects/{project_id}/report/generate")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "generated"
        assert payload["mock_mode"] is True
        assert payload["safety"]["uses_internal_router"] is True
        assert payload["safety"]["requires_api_keys"] is False
        assert payload["model_routing"]["tier"] == 3
        assert payload["model_routing"]["model"] == "mock-premium"
        assert payload["suppliers"]
        supplier_with_terms = next(item for item in payload["suppliers"] if item["terms"] is not None)
        assert supplier_with_terms["terms"]["moq"] == "Case pack orders"
        assert supplier_with_terms["terms"]["payment_terms"] == "Pro forma before dispatch"
        assert supplier_with_terms["evidence_urls"] == ["https://example.test/cardtrade-wholesale/pokemon"]

        with session_factory() as db:
            report_memory = db.scalar(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == "final_supplier_report")
            )
            agent_run = db.scalar(select(AgentRun).where(AgentRun.task_type == "final_report_generation"))

        assert report_memory.value["project_id"] == project_id
        assert agent_run.provider == "mock"
        assert agent_run.model == "mock-premium"
        assert agent_run.actual_cost_usd == 0


def test_get_report_returns_stored_report_without_duplicate_generation() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_suppliers_and_terms(client, session_factory)
        first_response = client.post(f"/projects/{project_id}/report/generate")
        second_response = client.get(f"/projects/{project_id}/report")

        assert first_response.status_code == 200
        assert second_response.status_code == 200
        assert second_response.json()["summary"] == first_response.json()["summary"]
        with session_factory() as db:
            runs = db.scalars(select(AgentRun).where(AgentRun.task_type == "final_report_generation")).all()
        assert len(runs) == 1


def test_csv_export_includes_status_scores_terms_and_source_references() -> None:
    with make_test_client() as (client, session_factory):
        project_id = create_project_with_suppliers_and_terms(client, session_factory)

        response = client.get(f"/projects/{project_id}/export.csv")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        rows = list(csv.DictReader(StringIO(response.text)))
        assert rows
        email_supplier = next(row for row in rows if row["contact_method"] == "email")
        assert email_supplier["status"] == "Email Drafted"
        assert email_supplier["trust_score"]
        assert email_supplier["relevance_score"]
        assert email_supplier["moq"] == "Case pack orders"
        assert email_supplier["price_list_available"] == "True"
        assert email_supplier["payment_terms"] == "Pro forma before dispatch"
        assert email_supplier["source_references"] == "https://example.test/cardtrade-wholesale/pokemon"


def test_report_generation_works_without_suppliers_or_api_keys() -> None:
    with make_test_client() as (client, _session_factory):
        create_response = client.post(
            "/projects/from-chat",
            json={"message": "Find Pokemon TCG distributors in the UK or EU."},
        )
        project_id = create_response.json()["project_id"]

        response = client.post(f"/projects/{project_id}/report/generate")

        assert response.status_code == 200
        payload = response.json()
        assert payload["summary"] == "Shortlisted 0 supplier candidates with evidence references and extracted terms."
        assert payload["suppliers"] == []
        assert payload["model_routing"]["provider"] == "mock"


def test_report_generation_requires_existing_project() -> None:
    with make_test_client() as (client, _session_factory):
        response = client.post("/projects/999/report/generate")

        assert response.status_code == 404
