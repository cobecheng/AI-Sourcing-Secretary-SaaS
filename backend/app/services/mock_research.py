from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AgentRun,
    ApprovalRequest,
    ChatMessage,
    ContactForm,
    Conversation,
    Milestone,
    OutreachMessage,
    Project,
    Supplier,
    SupplierSource,
    WorkflowRun,
)
from app.schemas.research import (
    ApprovalSummary,
    MilestoneSummary,
    MockResearchStartResponse,
    ResearchStatusResponse,
    SupplierEvidenceSummary,
    SupplierSummary,
    WorkflowSummary,
)


MOCK_SUPPLIERS: list[dict[str, Any]] = [
    {
        "name": "CardTrade Wholesale UK",
        "website": "https://example.test/cardtrade-wholesale",
        "country": "United Kingdom",
        "email": "trade@example.test",
        "supplier_type": "Distributor",
        "contact_method": "email",
        "trust_score": Decimal("0.7800"),
        "relevance_score": Decimal("0.9100"),
        "status": "Email Drafted",
        "notes": "Mock supplier that appears to stock sealed TCG products and asks for retailer details.",
        "source": {
            "url": "https://example.test/cardtrade-wholesale/pokemon",
            "title": "Pokemon sealed product trade catalogue",
            "snippet": "Evidence placeholder: wholesale Pokemon booster boxes and ETBs listed for trade accounts.",
            "source_type": "mock_search_result",
        },
    },
    {
        "name": "EU TCG Distribution",
        "website": "https://example.test/eu-tcg-distribution",
        "country": "Netherlands",
        "email": None,
        "supplier_type": "Distributor",
        "contact_method": "contact_form",
        "trust_score": Decimal("0.7300"),
        "relevance_score": Decimal("0.8700"),
        "status": "Contact Form Found",
        "notes": "Mock supplier with a wholesale inquiry form and no direct email shown.",
        "source": {
            "url": "https://example.test/eu-tcg-distribution/contact",
            "title": "Wholesale inquiry contact form",
            "snippet": "Evidence placeholder: contact form requests store name, country, monthly volume, and product category.",
            "source_type": "mock_form_detection",
        },
        "form": {
            "form_url": "https://example.test/eu-tcg-distribution/contact",
            "form_type": "wholesale_inquiry",
            "fields_json": {
                "required": ["business_name", "contact_name", "business_email", "country", "monthly_order_size"],
                "optional": ["store_website", "message"],
            },
        },
    },
    {
        "name": "Specialist Cards Import",
        "website": "https://example.test/specialist-cards-import",
        "country": "United Kingdom",
        "email": None,
        "supplier_type": "Importer",
        "contact_method": "manual_review",
        "trust_score": Decimal("0.6100"),
        "relevance_score": Decimal("0.7200"),
        "status": "Manual Review Needed",
        "notes": "Mock supplier with partial evidence. Human review is required before any outreach draft.",
        "source": {
            "url": "https://example.test/specialist-cards-import/trade",
            "title": "Trade account page",
            "snippet": "Evidence placeholder: trade page mentions TCG imports but does not confirm Pokemon allocation access.",
            "source_type": "mock_verification_gap",
        },
    },
]


def run_mock_research(db: Session, project_id: int) -> MockResearchStartResponse:
    project = _get_project(db, project_id)
    agent_run = _get_or_create_agent_run(db, project)
    workflow = _get_or_create_workflow_run(db, project, agent_run)

    project.status = "mock_research_ready_for_approval"
    agent_run.status = "complete"
    agent_run.output_json = {
        "mock_mode": True,
        "supplier_count": len(MOCK_SUPPLIERS),
        "approval_count": 2,
        "outbound_actions_performed": 0,
    }
    workflow.status = "waiting_for_approval"
    workflow.current_node = "human_approval"
    workflow.output_json = agent_run.output_json

    conversation = _get_project_conversation(db, project)
    _upsert_milestone(
        db,
        project,
        name="suppliers_discovered",
        status="complete",
        summary="Mock search found 38 potential supplier websites and shortlisted 3.",
        metadata_json={"mock_mode": True, "candidate_count": 38, "shortlisted_count": 3},
    )
    _add_once_message(
        db,
        conversation,
        content="Milestone complete: I found 38 mock supplier candidates and shortlisted 3 for verification.",
        metadata_json={"milestone": "suppliers_discovered", "mock_mode": True},
    )

    suppliers = [_upsert_supplier_bundle(db, project, supplier_data) for supplier_data in MOCK_SUPPLIERS]
    _upsert_milestone(
        db,
        project,
        name="suppliers_verified",
        status="complete",
        summary="Mock verification added evidence placeholders, scores, and preferred contact methods.",
        metadata_json={"mock_mode": True, "verified_count": len(suppliers)},
    )
    _add_once_message(
        db,
        conversation,
        content="Milestone complete: I verified the mock supplier cards and added evidence placeholders.",
        metadata_json={"milestone": "suppliers_verified", "mock_mode": True},
    )

    _upsert_outreach_draft(db, project, suppliers[0])
    _upsert_approval_requests(db, project, agent_run, suppliers)
    _upsert_milestone(
        db,
        project,
        name="outreach_approval",
        status="pending_user",
        summary="Draft approvals are ready. No email, form submission, or browser action has been performed.",
        metadata_json={"mock_mode": True, "approval_count": 2, "outbound_actions_performed": 0},
    )
    _add_once_message(
        db,
        conversation,
        content="I prepared mock approval cards for review. Nothing has been sent or submitted.",
        metadata_json={"milestone": "outreach_approval", "mock_mode": True, "requires_human_approval": True},
    )

    db.commit()
    return _build_status_response(db, project.id, message="Mock sourcing workflow completed and is waiting for approval.")


def get_mock_research_status(db: Session, project_id: int) -> ResearchStatusResponse:
    project = _get_project(db, project_id)
    response = _build_status_response(db, project.id)
    return ResearchStatusResponse(**response.model_dump(exclude={"message"}))


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_project_conversation(db: Session, project: Project) -> Conversation:
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project.id).order_by(Conversation.id))
    if conversation is None:
        conversation = Conversation(project_id=project.id, user_id=project.user_id)
        db.add(conversation)
        db.flush()
    return conversation


def _get_or_create_agent_run(db: Session, project: Project) -> AgentRun:
    agent_run = db.scalar(
        select(AgentRun)
        .where(AgentRun.project_id == project.id, AgentRun.task_type == "mock_sourcing_workflow")
        .order_by(AgentRun.id)
    )
    if agent_run is not None:
        return agent_run

    agent_run = AgentRun(
        project_id=project.id,
        agent_type="mock_sourcing_secretary",
        task_type="mock_sourcing_workflow",
        status="running",
        input_json={"project_id": project.id, "mock_mode": True},
        provider="mock",
        model="deterministic-fixture",
        estimated_cost_usd=Decimal("0.000000"),
        actual_cost_usd=Decimal("0.000000"),
        confidence=Decimal("0.8200"),
        fallback_used=False,
    )
    db.add(agent_run)
    db.flush()
    return agent_run


def _get_or_create_workflow_run(db: Session, project: Project, agent_run: AgentRun) -> WorkflowRun:
    key = f"mock-sourcing:{project.id}"
    workflow = db.scalar(select(WorkflowRun).where(WorkflowRun.idempotency_key == key))
    if workflow is not None:
        workflow.agent_run_id = agent_run.id
        return workflow

    workflow = WorkflowRun(
        project_id=project.id,
        agent_run_id=agent_run.id,
        workflow_name="mock_sourcing_workflow",
        current_node="search",
        status="running",
        idempotency_key=key,
        input_json={"project_id": project.id, "mock_mode": True},
    )
    db.add(workflow)
    db.flush()
    return workflow


def _upsert_milestone(
    db: Session,
    project: Project,
    name: str,
    status: str,
    summary: str,
    metadata_json: dict[str, Any],
) -> Milestone:
    milestone = db.scalar(select(Milestone).where(Milestone.project_id == project.id, Milestone.name == name))
    if milestone is None:
        milestone = Milestone(project_id=project.id, name=name)
        db.add(milestone)
    milestone.status = status
    milestone.summary = summary
    milestone.metadata_json = metadata_json
    if status == "complete" and milestone.completed_at is None:
        milestone.completed_at = datetime.now(UTC)
    db.flush()
    return milestone


def _upsert_supplier_bundle(db: Session, project: Project, supplier_data: dict[str, Any]) -> Supplier:
    supplier = db.scalar(select(Supplier).where(Supplier.project_id == project.id, Supplier.name == supplier_data["name"]))
    if supplier is None:
        supplier = Supplier(project_id=project.id, name=supplier_data["name"])
        db.add(supplier)

    for field in (
        "website",
        "country",
        "email",
        "supplier_type",
        "contact_method",
        "trust_score",
        "relevance_score",
        "status",
        "notes",
    ):
        setattr(supplier, field, supplier_data[field])
    db.flush()

    source_data = supplier_data["source"]
    source = db.scalar(
        select(SupplierSource).where(SupplierSource.supplier_id == supplier.id, SupplierSource.url == source_data["url"])
    )
    if source is None:
        source = SupplierSource(supplier_id=supplier.id, url=source_data["url"])
        db.add(source)
    source.title = source_data["title"]
    source.snippet = source_data["snippet"]
    source.extracted_text = "Mock-only evidence placeholder. Replace with crawler output after real search is enabled."
    source.source_type = source_data["source_type"]

    form_data = supplier_data.get("form")
    if form_data is not None:
        form = db.scalar(
            select(ContactForm).where(ContactForm.supplier_id == supplier.id, ContactForm.form_url == form_data["form_url"])
        )
        if form is None:
            form = ContactForm(supplier_id=supplier.id, form_url=form_data["form_url"])
            db.add(form)
        form.form_type = form_data["form_type"]
        form.fields_json = form_data["fields_json"]
        form.requires_captcha = False
        form.requires_login = False
        form.status = "detected"

    db.flush()
    return supplier


def _upsert_outreach_draft(db: Session, project: Project, supplier: Supplier) -> OutreachMessage:
    key = f"mock-email-draft:{project.id}:{supplier.id}"
    outreach = db.scalar(select(OutreachMessage).where(OutreachMessage.idempotency_key == key))
    if outreach is None:
        outreach = OutreachMessage(
            project_id=project.id,
            supplier_id=supplier.id,
            channel="email",
            idempotency_key=key,
        )
        db.add(outreach)

    outreach.subject = "Wholesale Pokemon TCG account inquiry"
    outreach.body = (
        "Hello CardTrade Wholesale UK,\n\n"
        "I run a small retail business and would like to ask about wholesale access for Pokemon TCG sealed products, "
        "including booster boxes and ETBs. Could you share your account requirements, MOQ, price list availability, "
        "and UK shipping terms?\n\n"
        "Best,\nMock Retailer"
    )
    outreach.status = "pending_approval"
    outreach.approved_by_user = False
    outreach.sent_at = None
    db.flush()
    return outreach


def _upsert_approval_requests(
    db: Session,
    project: Project,
    agent_run: AgentRun,
    suppliers: list[Supplier],
) -> None:
    email_supplier = suppliers[0]
    form_supplier = suppliers[1]
    approval_specs = [
        {
            "supplier": email_supplier,
            "request_type": "send_email",
            "title": "Approve mock email draft to CardTrade Wholesale UK",
            "payload_json": {
                "action": "send_email",
                "channel": "email",
                "mock_mode": True,
                "outbound_actions_performed": 0,
                "recipient": email_supplier.email,
                "subject": "Wholesale Pokemon TCG account inquiry",
                "missing_fields": ["business legal name", "store website", "monthly order estimate"],
                "evidence": ["https://example.test/cardtrade-wholesale/pokemon"],
                "safety": "Approval only. The system will not send in mock mode.",
            },
        },
        {
            "supplier": form_supplier,
            "request_type": "submit_contact_form",
            "title": "Approve mock wholesale inquiry form payload",
            "payload_json": {
                "action": "submit_contact_form",
                "channel": "browser_form",
                "mock_mode": True,
                "outbound_actions_performed": 0,
                "form_url": "https://example.test/eu-tcg-distribution/contact",
                "missing_fields": ["business name", "business email", "store website", "monthly order size"],
                "evidence": ["https://example.test/eu-tcg-distribution/contact"],
                "safety": "Approval only. No browser submission is implemented in mock mode.",
            },
        },
    ]

    for spec in approval_specs:
        approval = db.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.project_id == project.id,
                ApprovalRequest.supplier_id == spec["supplier"].id,
                ApprovalRequest.request_type == spec["request_type"],
            )
        )
        if approval is None:
            approval = ApprovalRequest(
                project_id=project.id,
                supplier_id=spec["supplier"].id,
                request_type=spec["request_type"],
            )
            db.add(approval)
        approval.status = "pending"
        approval.title = spec["title"]
        approval.payload_json = spec["payload_json"]
        approval.decision_json = None
        approval.requested_by_agent_run_id = agent_run.id
        approval.decided_by_user_id = None
        approval.decided_at = None
    db.flush()


def _add_once_message(
    db: Session,
    conversation: Conversation,
    content: str,
    metadata_json: dict[str, Any],
) -> None:
    existing = db.scalar(
        select(ChatMessage).where(
            ChatMessage.conversation_id == conversation.id,
            ChatMessage.sender == "assistant",
            ChatMessage.message_type == "milestone_update",
            ChatMessage.content == content,
        )
    )
    if existing is not None:
        return
    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            sender="assistant",
            message_type="milestone_update",
            content=content,
            metadata_json=metadata_json,
        )
    )
    db.flush()


def _build_status_response(db: Session, project_id: int, message: str = "") -> MockResearchStartResponse:
    project = _get_project(db, project_id)
    workflow = db.scalar(
        select(WorkflowRun)
        .where(WorkflowRun.project_id == project.id, WorkflowRun.workflow_name == "mock_sourcing_workflow")
        .order_by(WorkflowRun.id.desc())
    )
    milestones = db.scalars(select(Milestone).where(Milestone.project_id == project.id).order_by(Milestone.id)).all()
    suppliers = db.scalars(select(Supplier).where(Supplier.project_id == project.id).order_by(Supplier.relevance_score.desc())).all()
    approvals = db.scalars(
        select(ApprovalRequest).where(ApprovalRequest.project_id == project.id).order_by(ApprovalRequest.id)
    ).all()

    return MockResearchStartResponse(
        message=message,
        project_id=project.id,
        project_status=project.status,
        mock_mode=True,
        workflow=_workflow_summary(workflow),
        milestones=[
            MilestoneSummary(
                id=milestone.id,
                name=milestone.name,
                status=milestone.status,
                summary=milestone.summary,
                metadata_json=milestone.metadata_json,
            )
            for milestone in milestones
        ],
        suppliers=[_supplier_summary(db, supplier) for supplier in suppliers],
        approvals=[
            ApprovalSummary(
                id=approval.id,
                supplier_id=approval.supplier_id,
                request_type=approval.request_type,
                status=approval.status,
                title=approval.title,
                payload_json=approval.payload_json,
            )
            for approval in approvals
        ],
    )


def _workflow_summary(workflow: WorkflowRun | None) -> WorkflowSummary | None:
    if workflow is None:
        return None
    return WorkflowSummary(
        id=workflow.id,
        workflow_name=workflow.workflow_name,
        current_node=workflow.current_node,
        status=workflow.status,
        idempotency_key=workflow.idempotency_key,
    )


def _supplier_summary(db: Session, supplier: Supplier) -> SupplierSummary:
    sources = db.scalars(select(SupplierSource).where(SupplierSource.supplier_id == supplier.id).order_by(SupplierSource.id)).all()
    return SupplierSummary(
        id=supplier.id,
        name=supplier.name,
        website=supplier.website,
        country=supplier.country,
        email=supplier.email,
        supplier_type=supplier.supplier_type,
        contact_method=supplier.contact_method,
        trust_score=float(supplier.trust_score) if supplier.trust_score is not None else None,
        relevance_score=float(supplier.relevance_score) if supplier.relevance_score is not None else None,
        status=supplier.status,
        notes=supplier.notes,
        evidence=[
            SupplierEvidenceSummary(
                url=source.url,
                title=source.title,
                snippet=source.snippet,
                source_type=source.source_type,
            )
            for source in sources
        ],
    )
