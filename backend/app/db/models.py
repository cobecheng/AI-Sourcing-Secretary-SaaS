from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    false,
    func,
    true,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base
from app.db.types import id_type


JsonDict = dict[str, Any]
json_type = JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql")


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_user_id", "user_id"),
        Index("ix_projects_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    target_products: Mapped[JsonDict | None] = mapped_column(json_type)
    region: Mapped[str | None] = mapped_column(Text)
    budget: Mapped[JsonDict | None] = mapped_column(json_type)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")


class Conversation(TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_project_id", "project_id"),
        Index("ix_conversations_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (
        Index("ix_chat_messages_conversation_id", "conversation_id"),
        Index("ix_chat_messages_message_type", "message_type"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    sender: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[JsonDict | None] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Milestone(Base):
    __tablename__ = "milestones"
    __table_args__ = (
        Index("ix_milestones_project_id", "project_id"),
        Index("ix_milestones_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    summary: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[JsonDict | None] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectMemory(TimestampMixin, Base):
    __tablename__ = "project_memory"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_project_memory_project_key"),
        Index("ix_project_memory_project_id", "project_id"),
        Index("ix_project_memory_source_message_id", "source_message_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[JsonDict] = mapped_column(json_type, nullable=False)
    source_message_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id", ondelete="SET NULL"))


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        Index("ix_suppliers_project_id", "project_id"),
        Index("ix_suppliers_status", "status"),
        Index("ix_suppliers_website", "website"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    supplier_type: Mapped[str | None] = mapped_column(Text)
    contact_method: Mapped[str | None] = mapped_column(Text)
    trust_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    relevance_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="Discovered")
    notes: Mapped[str | None] = mapped_column(Text)


class SupplierSource(Base):
    __tablename__ = "supplier_sources"
    __table_args__ = (
        Index("ix_supplier_sources_supplier_id", "supplier_id"),
        Index("ix_supplier_sources_url", "url"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ContactForm(TimestampMixin, Base):
    __tablename__ = "contact_forms"
    __table_args__ = (
        Index("ix_contact_forms_supplier_id", "supplier_id"),
        Index("ix_contact_forms_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    form_url: Mapped[str] = mapped_column(Text, nullable=False)
    form_type: Mapped[str | None] = mapped_column(Text)
    fields_json: Mapped[JsonDict] = mapped_column(json_type, nullable=False)
    requires_captcha: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    requires_login: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="detected")


class FormSubmission(Base):
    __tablename__ = "form_submissions"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_form_submissions_idempotency_key"),
        Index("ix_form_submissions_supplier_id", "supplier_id"),
        Index("ix_form_submissions_contact_form_id", "contact_form_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    contact_form_id: Mapped[int] = mapped_column(ForeignKey("contact_forms.id", ondelete="CASCADE"), nullable=False)
    submitted_payload_json: Mapped[JsonDict] = mapped_column(json_type, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    approved_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    screenshot_before_url: Mapped[str | None] = mapped_column(Text)
    screenshot_after_url: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OutreachMessage(Base):
    __tablename__ = "outreach_messages"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outreach_messages_idempotency_key"),
        Index("ix_outreach_messages_project_id", "project_id"),
        Index("ix_outreach_messages_supplier_id", "supplier_id"),
        Index("ix_outreach_messages_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="draft")
    approved_by_user: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class EmailThread(Base):
    __tablename__ = "email_threads"
    __table_args__ = (
        UniqueConstraint("gmail_thread_id", name="uq_email_threads_gmail_thread_id"),
        Index("ix_email_threads_supplier_id", "supplier_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    gmail_thread_id: Mapped[str] = mapped_column(Text, nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SupplierTerm(Base):
    __tablename__ = "supplier_terms"
    __table_args__ = (
        Index("ix_supplier_terms_supplier_id", "supplier_id"),
        Index("ix_supplier_terms_extracted_from_message_id", "extracted_from_message_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    moq: Mapped[str | None] = mapped_column(Text)
    price_list_available: Mapped[bool | None] = mapped_column(Boolean)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    shipping_regions: Mapped[JsonDict | None] = mapped_column(json_type)
    lead_time: Mapped[str | None] = mapped_column(Text)
    account_requirements: Mapped[str | None] = mapped_column(Text)
    extracted_from_message_id: Mapped[int | None] = mapped_column(ForeignKey("chat_messages.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgentRun(TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_agent_runs_project_id", "project_id"),
        Index("ix_agent_runs_task_type", "task_type"),
        Index("ix_agent_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_type: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    input_json: Mapped[JsonDict | None] = mapped_column(json_type)
    output_json: Mapped[JsonDict | None] = mapped_column(json_type)
    error: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str | None] = mapped_column(Text)
    model: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    actual_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    latency_ms: Mapped[int | None] = mapped_column(BigInteger)
    prompt_version: Mapped[str | None] = mapped_column(Text)
    schema_version: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())


class ApprovalRequest(TimestampMixin, Base):
    __tablename__ = "approval_requests"
    __table_args__ = (
        Index("ix_approval_requests_project_id", "project_id"),
        Index("ix_approval_requests_supplier_id", "supplier_id"),
        Index("ix_approval_requests_status", "status"),
        Index("ix_approval_requests_requested_by_agent_run_id", "requested_by_agent_run_id"),
        Index("ix_approval_requests_decided_by_user_id", "decided_by_user_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"))
    request_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    title: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[JsonDict] = mapped_column(json_type, nullable=False)
    decision_json: Mapped[JsonDict | None] = mapped_column(json_type)
    requested_by_agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    decided_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkflowRun(TimestampMixin, Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_workflow_runs_idempotency_key"),
        Index("ix_workflow_runs_project_id", "project_id"),
        Index("ix_workflow_runs_agent_run_id", "agent_run_id"),
        Index("ix_workflow_runs_status", "status"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="SET NULL"))
    workflow_name: Mapped[str] = mapped_column(Text, nullable=False)
    current_node: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[JsonDict | None] = mapped_column(json_type)
    output_json: Mapped[JsonDict | None] = mapped_column(json_type)
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_user_id", "user_id"),
        Index("ix_audit_logs_project_id", "project_id"),
        Index("ix_audit_logs_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    metadata_json: Mapped[JsonDict | None] = mapped_column(json_type)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LLMBudget(TimestampMixin, Base):
    __tablename__ = "llm_budgets"
    __table_args__ = (
        Index("ix_llm_budgets_user_id", "user_id"),
        Index("ix_llm_budgets_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    daily_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="2")
    monthly_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="20")
    project_limit_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="5")
    premium_call_limit: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="5")
    current_daily_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    current_monthly_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")
    current_project_spend_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, server_default="0")


class LLMModelConfig(TimestampMixin, Base):
    __tablename__ = "llm_model_configs"
    __table_args__ = (
        Index("ix_llm_model_configs_task_type", "task_type"),
        Index("ix_llm_model_configs_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    tier: Mapped[int] = mapped_column(BigInteger, nullable=False)
    provider: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="100")
    max_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    max_output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    max_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 6))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=true())
