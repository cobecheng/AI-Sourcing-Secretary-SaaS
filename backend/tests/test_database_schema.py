from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db.base import Base
from app.db import models  # noqa: F401


EXPECTED_TABLES = {
    "users",
    "projects",
    "conversations",
    "chat_messages",
    "milestones",
    "project_memory",
    "suppliers",
    "supplier_sources",
    "contact_forms",
    "form_submissions",
    "outreach_messages",
    "email_threads",
    "supplier_terms",
    "agent_runs",
    "approval_requests",
    "workflow_runs",
    "audit_logs",
    "llm_budgets",
    "llm_model_configs",
}


def test_model_metadata_includes_core_tables() -> None:
    assert EXPECTED_TABLES.issubset(set(Base.metadata.tables))


def test_approval_and_workflow_tables_are_first_class() -> None:
    approval_columns = set(Base.metadata.tables["approval_requests"].columns.keys())
    workflow_columns = set(Base.metadata.tables["workflow_runs"].columns.keys())

    assert {"project_id", "request_type", "status", "payload_json"}.issubset(approval_columns)
    assert {"project_id", "workflow_name", "status", "idempotency_key"}.issubset(workflow_columns)


def test_foreign_key_columns_have_indexes() -> None:
    for table in Base.metadata.tables.values():
        indexed_columns = {
            column.name
            for index in table.indexes
            for column in index.columns
        }
        for foreign_key in table.foreign_keys:
            column_name = foreign_key.parent.name
            assert column_name in indexed_columns or column_name == "user_id" and table.name == "users"


def test_migration_smoke_applies_to_fresh_database(tmp_path: Path) -> None:
    database_path = tmp_path / "migration-smoke.db"
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("script_location", "alembic")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(alembic_cfg, "head")

    engine = create_engine(f"sqlite:///{database_path}")
    inspector = inspect(engine)

    assert EXPECTED_TABLES.issubset(set(inspector.get_table_names()))
    assert "approval_requests" in inspector.get_table_names()
    assert "workflow_runs" in inspector.get_table_names()
