from datetime import UTC, datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AgentRun, ChatMessage, Conversation, LLMBudget, Project
from app.schemas.llm import (
    AgentRunUsageResponse,
    LLMBudgetResponse,
    LLMCompleteRequest,
    LLMCompleteResponse,
    LLMUsageResponse,
)
from app.services.llm_router import route_llm_call


BUDGET_WARNING_RATIO = Decimal("0.80")
EXPENSIVE_TASKS = {
    "email_drafting",
    "supplier_relevance_scoring",
    "supplier_trust_scoring",
    "supplier_website_extraction",
    "final_report_generation",
}


def complete_with_mock_llm(db: Session, request: LLMCompleteRequest) -> LLMCompleteResponse:
    project = _get_project(db, request.project_id)
    routed_call = route_llm_call(request)
    budget = _get_or_create_project_budget(db, project)
    call_cost = Decimal(str(request.actual_cost_usd if request.actual_cost_usd is not None else request.estimated_cost_usd))
    was_already_warning = _is_budget_warning(budget)
    projected_spend = Decimal(str(budget.current_project_spend_usd or 0)) + call_cost

    if _is_budget_exceeded(projected_spend, Decimal(str(budget.project_limit_usd))) and _is_expensive_task(request.task_type):
        warning_created = _create_budget_chat_message(
            db,
            project,
            message=(
                "Budget limit reached. I paused this expensive model task and need approval before continuing "
                "with paid or higher-cost model calls."
            ),
            message_type="budget_pause",
            metadata_json={"budget_status": "paused", "task_type": request.task_type, "mock_mode": True},
        )
        db.commit()
        return LLMCompleteResponse(
            agent_run=None,
            budget=_budget_response(budget),
            status="paused_for_budget",
            message="Expensive task paused because the project budget would be exceeded.",
            routing=_routing_payload(routed_call),
            chat_warning_created=warning_created,
            requires_user_approval=True,
        )

    agent_run = AgentRun(
        project_id=project.id,
        agent_type="llm_router",
        task_type=request.task_type,
        status="needs_user_approval" if routed_call.requires_user_approval else "complete",
        input_json={
            "prompt": request.prompt,
            "input": request.input_json,
            "required_output_fields": request.required_output_fields,
            "mock_mode": get_settings().mock_mode,
            "routing": _routing_payload(routed_call),
        },
        output_json={**routed_call.output_json, "budget_checked": True},
        provider=routed_call.provider,
        model=routed_call.model,
        input_tokens=request.input_tokens,
        output_tokens=request.output_tokens,
        estimated_cost_usd=Decimal(str(request.estimated_cost_usd)),
        actual_cost_usd=call_cost,
        latency_ms=request.latency_ms,
        prompt_version=routed_call.prompt_version,
        schema_version=routed_call.schema_version,
        confidence=Decimal(str(routed_call.confidence)),
        fallback_used=routed_call.fallback_used,
    )
    db.add(agent_run)
    _apply_budget_spend(budget, call_cost)

    warning_created = False
    if _is_budget_warning(budget) and not was_already_warning and not _has_budget_message(db, project.id, "budget_warning_80"):
        warning_created = _create_budget_chat_message(
            db,
            project,
            message=(
                "Heads up: this project has reached 80 percent of its model budget. I will keep using mock, "
                "cheap, or local model paths unless you approve more expensive work."
            ),
            message_type="budget_warning",
            metadata_json={"budget_status": "warning_80", "mock_mode": True},
        )

    db.commit()
    db.refresh(agent_run)
    db.refresh(budget)
    return LLMCompleteResponse(
        agent_run=_agent_run_response(agent_run),
        budget=_budget_response(budget),
        status=_budget_status(budget),
        message="Mock LLM call routed and logged with budget usage.",
        routing=_routing_payload(routed_call),
        chat_warning_created=warning_created,
        requires_user_approval=routed_call.requires_user_approval,
    )


def get_project_usage(db: Session, project_id: int) -> LLMUsageResponse:
    project = _get_project(db, project_id)
    budget = _get_or_create_project_budget(db, project)
    runs = _project_runs(db, project.id)
    return _usage_response(scope="project", scope_id=project.id, budget=budget, runs=runs)


def get_user_usage(db: Session, user_id: int) -> LLMUsageResponse:
    runs = db.scalars(select(AgentRun).join(Project, AgentRun.project_id == Project.id).where(Project.user_id == user_id).order_by(AgentRun.id)).all()
    budget = db.scalar(select(LLMBudget).where(LLMBudget.user_id == user_id, LLMBudget.project_id.is_(None)).order_by(LLMBudget.id))
    return _usage_response(scope="user", scope_id=user_id, budget=budget, runs=runs)


def get_project_budget(db: Session, project_id: int) -> LLMBudgetResponse:
    project = _get_project(db, project_id)
    return _budget_response(_get_or_create_project_budget(db, project))


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_or_create_project_budget(db: Session, project: Project) -> LLMBudget:
    budget = db.scalar(select(LLMBudget).where(LLMBudget.project_id == project.id).order_by(LLMBudget.id))
    if budget is not None:
        return budget

    settings = get_settings()
    budget = LLMBudget(
        user_id=project.user_id,
        project_id=project.id,
        daily_limit_usd=Decimal(str(settings.max_user_daily_llm_cost_usd)),
        monthly_limit_usd=Decimal(str(settings.max_user_daily_llm_cost_usd * 30)),
        project_limit_usd=Decimal(str(settings.max_project_llm_cost_usd)),
        premium_call_limit=settings.max_premium_calls_per_project,
        current_daily_spend_usd=Decimal("0"),
        current_monthly_spend_usd=Decimal("0"),
        current_project_spend_usd=Decimal("0"),
    )
    db.add(budget)
    db.flush()
    return budget


def _apply_budget_spend(budget: LLMBudget, amount: Decimal) -> None:
    budget.current_daily_spend_usd = Decimal(str(budget.current_daily_spend_usd or 0)) + amount
    budget.current_monthly_spend_usd = Decimal(str(budget.current_monthly_spend_usd or 0)) + amount
    budget.current_project_spend_usd = Decimal(str(budget.current_project_spend_usd or 0)) + amount


def _is_expensive_task(task_type: str) -> bool:
    return task_type in EXPENSIVE_TASKS


def _is_budget_exceeded(spend: Decimal, limit: Decimal) -> bool:
    return limit > 0 and spend > limit


def _is_budget_warning(budget: LLMBudget) -> bool:
    limit = Decimal(str(budget.project_limit_usd))
    spend = Decimal(str(budget.current_project_spend_usd))
    return limit > 0 and spend >= limit * BUDGET_WARNING_RATIO


def _budget_status(budget: LLMBudget) -> str:
    limit = Decimal(str(budget.project_limit_usd))
    spend = Decimal(str(budget.current_project_spend_usd))
    if _is_budget_exceeded(spend, limit):
        return "exceeded"
    if limit > 0 and spend >= limit * BUDGET_WARNING_RATIO:
        return "warning_80"
    return "ok"


def _has_budget_message(db: Session, project_id: int, budget_status: str) -> bool:
    conversation_ids = db.scalars(select(Conversation.id).where(Conversation.project_id == project_id)).all()
    if not conversation_ids:
        return False
    messages = db.scalars(
        select(ChatMessage)
        .where(
            ChatMessage.conversation_id.in_(conversation_ids),
            ChatMessage.message_type.in_(("budget_warning", "budget_pause")),
        )
    ).all()
    if budget_status == "warning_80":
        return any(message.message_type == "budget_warning" for message in messages)
    return any((message.metadata_json or {}).get("budget_status") == budget_status for message in messages)


def _create_budget_chat_message(
    db: Session,
    project: Project,
    message: str,
    message_type: str,
    metadata_json: dict,
) -> bool:
    conversation = db.scalar(select(Conversation).where(Conversation.project_id == project.id).order_by(Conversation.id))
    if conversation is None:
        conversation = Conversation(project_id=project.id, user_id=project.user_id)
        db.add(conversation)
        db.flush()

    db.add(
        ChatMessage(
            conversation_id=conversation.id,
            sender="assistant",
            message_type=message_type,
            content=message,
            metadata_json={**metadata_json, "created_at": datetime.now(UTC).isoformat()},
        )
    )
    db.flush()
    return True


def _project_runs(db: Session, project_id: int) -> list[AgentRun]:
    return db.scalars(select(AgentRun).where(AgentRun.project_id == project_id).order_by(AgentRun.id)).all()


def _usage_response(scope: str, scope_id: int, budget: LLMBudget | None, runs: list[AgentRun]) -> LLMUsageResponse:
    return LLMUsageResponse(
        scope=scope,
        id=scope_id,
        budget=_budget_response(budget) if budget is not None else None,
        total_estimated_cost_usd=sum(float(run.estimated_cost_usd or 0) for run in runs),
        total_actual_cost_usd=sum(float(run.actual_cost_usd or 0) for run in runs),
        total_input_tokens=sum(run.input_tokens or 0 for run in runs),
        total_output_tokens=sum(run.output_tokens or 0 for run in runs),
        runs=[_agent_run_response(run) for run in runs],
    )


def _agent_run_response(run: AgentRun) -> AgentRunUsageResponse:
    return AgentRunUsageResponse(
        id=run.id,
        project_id=run.project_id,
        task_type=run.task_type,
        status=run.status,
        provider=run.provider,
        model=run.model,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        estimated_cost_usd=float(run.estimated_cost_usd) if run.estimated_cost_usd is not None else None,
        actual_cost_usd=float(run.actual_cost_usd) if run.actual_cost_usd is not None else None,
        latency_ms=run.latency_ms,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        confidence=float(run.confidence) if run.confidence is not None else None,
        fallback_used=run.fallback_used,
    )


def _budget_response(budget: LLMBudget) -> LLMBudgetResponse:
    limit = float(budget.project_limit_usd)
    spend = float(budget.current_project_spend_usd)
    return LLMBudgetResponse(
        id=budget.id,
        user_id=budget.user_id,
        project_id=budget.project_id,
        daily_limit_usd=float(budget.daily_limit_usd),
        monthly_limit_usd=float(budget.monthly_limit_usd),
        project_limit_usd=limit,
        premium_call_limit=budget.premium_call_limit,
        current_daily_spend_usd=float(budget.current_daily_spend_usd),
        current_monthly_spend_usd=float(budget.current_monthly_spend_usd),
        current_project_spend_usd=spend,
        project_budget_ratio=spend / limit if limit else 0,
        status=_budget_status(budget),
    )


def _routing_payload(routed_call) -> dict:
    return {
        "provider": routed_call.provider,
        "model": routed_call.model,
        "tier": routed_call.tier,
        "confidence": routed_call.confidence,
        "prompt_version": routed_call.prompt_version,
        "schema_version": routed_call.schema_version,
        "fallback_used": routed_call.fallback_used,
        "requires_user_approval": routed_call.requires_user_approval,
        "decision": routed_call.decision,
        "reason": routed_call.reason,
    }
