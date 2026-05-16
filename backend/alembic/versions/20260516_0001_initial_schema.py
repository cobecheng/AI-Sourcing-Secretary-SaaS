"""initial schema

Revision ID: 20260516_0001
Revises:
Create Date: 2026-05-16
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260516_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def pk_column() -> sa.Column:
    return sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True)


def timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        pk_column(),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "projects",
        pk_column(),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("target_products", json_type(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("budget", json_type(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        *timestamps(),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    op.create_table(
        "conversations",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        *timestamps(),
    )
    op.create_index("ix_conversations_project_id", "conversations", ["project_id"])
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "chat_messages",
        pk_column(),
        sa.Column("conversation_id", sa.BigInteger(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.Text(), nullable=False),
        sa.Column("message_type", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_json", json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chat_messages_conversation_id", "chat_messages", ["conversation_id"])
    op.create_index("ix_chat_messages_message_type", "chat_messages", ["message_type"])

    op.create_table(
        "milestones",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("metadata_json", json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_milestones_project_id", "milestones", ["project_id"])
    op.create_index("ix_milestones_status", "milestones", ["status"])

    op.create_table(
        "project_memory",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", json_type(), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("project_id", "key", name="uq_project_memory_project_key"),
    )
    op.create_index("ix_project_memory_project_id", "project_memory", ["project_id"])
    op.create_index("ix_project_memory_source_message_id", "project_memory", ["source_message_id"])

    op.create_table(
        "suppliers",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("country", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("supplier_type", sa.Text(), nullable=True),
        sa.Column("contact_method", sa.Text(), nullable=True),
        sa.Column("trust_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("relevance_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="Discovered"),
        sa.Column("notes", sa.Text(), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_suppliers_project_id", "suppliers", ["project_id"])
    op.create_index("ix_suppliers_status", "suppliers", ["status"])
    op.create_index("ix_suppliers_website", "suppliers", ["website"])

    op.create_table(
        "supplier_sources",
        pk_column(),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_sources_supplier_id", "supplier_sources", ["supplier_id"])
    op.create_index("ix_supplier_sources_url", "supplier_sources", ["url"])

    op.create_table(
        "contact_forms",
        pk_column(),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("form_url", sa.Text(), nullable=False),
        sa.Column("form_type", sa.Text(), nullable=True),
        sa.Column("fields_json", json_type(), nullable=False),
        sa.Column("requires_captcha", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("requires_login", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.Text(), nullable=False, server_default="detected"),
        *timestamps(),
    )
    op.create_index("ix_contact_forms_supplier_id", "contact_forms", ["supplier_id"])
    op.create_index("ix_contact_forms_status", "contact_forms", ["status"])

    op.create_table(
        "form_submissions",
        pk_column(),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("contact_form_id", sa.BigInteger(), sa.ForeignKey("contact_forms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_payload_json", json_type(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("approved_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("screenshot_before_url", sa.Text(), nullable=True),
        sa.Column("screenshot_after_url", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_form_submissions_idempotency_key"),
    )
    op.create_index("ix_form_submissions_supplier_id", "form_submissions", ["supplier_id"])
    op.create_index("ix_form_submissions_contact_form_id", "form_submissions", ["contact_form_id"])

    op.create_table(
        "outreach_messages",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("approved_by_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_outreach_messages_idempotency_key"),
    )
    op.create_index("ix_outreach_messages_project_id", "outreach_messages", ["project_id"])
    op.create_index("ix_outreach_messages_supplier_id", "outreach_messages", ["supplier_id"])
    op.create_index("ix_outreach_messages_status", "outreach_messages", ["status"])

    op.create_table(
        "email_threads",
        pk_column(),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("gmail_thread_id", sa.Text(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("gmail_thread_id", name="uq_email_threads_gmail_thread_id"),
    )
    op.create_index("ix_email_threads_supplier_id", "email_threads", ["supplier_id"])

    op.create_table(
        "supplier_terms",
        pk_column(),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("moq", sa.Text(), nullable=True),
        sa.Column("price_list_available", sa.Boolean(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("shipping_regions", json_type(), nullable=True),
        sa.Column("lead_time", sa.Text(), nullable=True),
        sa.Column("account_requirements", sa.Text(), nullable=True),
        sa.Column("extracted_from_message_id", sa.BigInteger(), sa.ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_supplier_terms_supplier_id", "supplier_terms", ["supplier_id"])
    op.create_index("ix_supplier_terms_extracted_from_message_id", "supplier_terms", ["extracted_from_message_id"])

    op.create_table(
        "agent_runs",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_type", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("input_json", json_type(), nullable=True),
        sa.Column("output_json", json_type(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=True),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("actual_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("latency_ms", sa.BigInteger(), nullable=True),
        sa.Column("prompt_version", sa.Text(), nullable=True),
        sa.Column("schema_version", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), nullable=False, server_default=sa.false()),
        *timestamps(),
    )
    op.create_index("ix_agent_runs_project_id", "agent_runs", ["project_id"])
    op.create_index("ix_agent_runs_task_type", "agent_runs", ["task_type"])
    op.create_index("ix_agent_runs_status", "agent_runs", ["status"])

    op.create_table(
        "approval_requests",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.BigInteger(), sa.ForeignKey("suppliers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("payload_json", json_type(), nullable=False),
        sa.Column("decision_json", json_type(), nullable=True),
        sa.Column("requested_by_agent_run_id", sa.BigInteger(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by_user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
    )
    op.create_index("ix_approval_requests_project_id", "approval_requests", ["project_id"])
    op.create_index("ix_approval_requests_supplier_id", "approval_requests", ["supplier_id"])
    op.create_index("ix_approval_requests_status", "approval_requests", ["status"])
    op.create_index("ix_approval_requests_requested_by_agent_run_id", "approval_requests", ["requested_by_agent_run_id"])
    op.create_index("ix_approval_requests_decided_by_user_id", "approval_requests", ["decided_by_user_id"])

    op.create_table(
        "workflow_runs",
        pk_column(),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_run_id", sa.BigInteger(), sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("workflow_name", sa.Text(), nullable=False),
        sa.Column("current_node", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("input_json", json_type(), nullable=True),
        sa.Column("output_json", json_type(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("idempotency_key", name="uq_workflow_runs_idempotency_key"),
    )
    op.create_index("ix_workflow_runs_project_id", "workflow_runs", ["project_id"])
    op.create_index("ix_workflow_runs_agent_run_id", "workflow_runs", ["agent_run_id"])
    op.create_index("ix_workflow_runs_status", "workflow_runs", ["status"])

    op.create_table(
        "audit_logs",
        pk_column(),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.BigInteger(), nullable=True),
        sa.Column("metadata_json", json_type(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_project_id", "audit_logs", ["project_id"])
    op.create_index("ix_audit_logs_entity", "audit_logs", ["entity_type", "entity_id"])

    op.create_table(
        "llm_budgets",
        pk_column(),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.BigInteger(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("daily_limit_usd", sa.Numeric(12, 6), nullable=False, server_default="2"),
        sa.Column("monthly_limit_usd", sa.Numeric(12, 6), nullable=False, server_default="20"),
        sa.Column("project_limit_usd", sa.Numeric(12, 6), nullable=False, server_default="5"),
        sa.Column("premium_call_limit", sa.BigInteger(), nullable=False, server_default="5"),
        sa.Column("current_daily_spend_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("current_monthly_spend_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        sa.Column("current_project_spend_usd", sa.Numeric(12, 6), nullable=False, server_default="0"),
        *timestamps(),
    )
    op.create_index("ix_llm_budgets_user_id", "llm_budgets", ["user_id"])
    op.create_index("ix_llm_budgets_project_id", "llm_budgets", ["project_id"])

    op.create_table(
        "llm_model_configs",
        pk_column(),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("tier", sa.BigInteger(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("priority", sa.BigInteger(), nullable=False, server_default="100"),
        sa.Column("max_input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("max_output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("max_cost_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *timestamps(),
    )
    op.create_index("ix_llm_model_configs_task_type", "llm_model_configs", ["task_type"])
    op.create_index("ix_llm_model_configs_enabled", "llm_model_configs", ["enabled"])


def downgrade() -> None:
    for table_name in [
        "llm_model_configs",
        "llm_budgets",
        "audit_logs",
        "workflow_runs",
        "approval_requests",
        "agent_runs",
        "supplier_terms",
        "email_threads",
        "outreach_messages",
        "form_submissions",
        "contact_forms",
        "supplier_sources",
        "suppliers",
        "project_memory",
        "milestones",
        "chat_messages",
        "conversations",
        "projects",
        "users",
    ]:
        op.drop_table(table_name)
