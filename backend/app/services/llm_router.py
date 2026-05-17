from dataclasses import dataclass
from typing import Any

from app.schemas.llm import LLMCompleteRequest, LLMModelConfigResponse


CONFIDENCE_ACCEPT_THRESHOLD = 0.85
CONFIDENCE_VERIFY_THRESHOLD = 0.60
RISKY_TERMS = {
    "captcha",
    "contract",
    "document upload",
    "exclusivity",
    "legal",
    "login",
    "payment",
    "pricing commitment",
}


@dataclass(frozen=True)
class TaskRoute:
    task_type: str
    tier: int
    provider: str
    model: str
    priority: int = 100
    max_input_tokens: int | None = 4000
    max_output_tokens: int | None = 1000
    max_cost_usd: float | None = 0.0
    fallback_tier: int | None = None
    fallback_model: str | None = None
    schema_version: str = "mock-v1"


@dataclass(frozen=True)
class RoutedLLMCall:
    provider: str
    model: str
    tier: int
    confidence: float
    prompt_version: str
    schema_version: str
    fallback_used: bool
    requires_user_approval: bool
    decision: str
    reason: str
    output_json: dict[str, Any]


DEFAULT_TASK_ROUTES: dict[str, TaskRoute] = {
    "milestone_update": TaskRoute("milestone_update", tier=0, provider="mock", model="mock-cheap"),
    "intent_classification": TaskRoute("intent_classification", tier=0, provider="mock", model="mock-cheap"),
    "sourcing_request_extraction": TaskRoute("sourcing_request_extraction", tier=1, provider="mock", model="mock-cheap"),
    "search_query_generation": TaskRoute("search_query_generation", tier=1, provider="mock", model="mock-cheap"),
    "search_result_filtering": TaskRoute("search_result_filtering", tier=0, provider="mock", model="mock-cheap"),
    "supplier_website_extraction": TaskRoute("supplier_website_extraction", tier=1, provider="mock", model="mock-cheap"),
    "supplier_deduplication": TaskRoute("supplier_deduplication", tier=0, provider="mock", model="deterministic-code"),
    "supplier_relevance_scoring": TaskRoute("supplier_relevance_scoring", tier=2, provider="mock", model="mock-mid"),
    "supplier_trust_scoring": TaskRoute(
        "supplier_trust_scoring",
        tier=2,
        provider="mock",
        model="mock-mid",
        fallback_tier=3,
        fallback_model="mock-premium",
    ),
    "email_draft_generation": TaskRoute("email_draft_generation", tier=2, provider="mock", model="mock-mid"),
    "important_email_review": TaskRoute("important_email_review", tier=3, provider="mock", model="mock-premium"),
    "contact_form_field_mapping": TaskRoute("contact_form_field_mapping", tier=1, provider="mock", model="mock-cheap"),
    "browser_action_decision": TaskRoute(
        "browser_action_decision",
        tier=2,
        provider="mock",
        model="mock-mid",
        fallback_tier=3,
        fallback_model="mock-premium",
    ),
    "reply_parsing": TaskRoute("reply_parsing", tier=1, provider="mock", model="mock-cheap"),
    "final_report_generation": TaskRoute("final_report_generation", tier=3, provider="mock", model="mock-premium"),
}


def route_llm_call(request: LLMCompleteRequest) -> RoutedLLMCall:
    route = DEFAULT_TASK_ROUTES.get(
        request.task_type,
        TaskRoute(request.task_type, tier=1, provider="mock", model="mock-cheap"),
    )
    requested_confidence = request.confidence if request.confidence is not None else _mock_confidence_for_task(request.task_type)
    output_json = _mock_output_json(request)
    missing_fields = _missing_required_fields(output_json, request.required_output_fields)
    risky_reason = _risky_reason(request)

    if risky_reason is not None:
        return _routed(
            request,
            route,
            confidence=requested_confidence,
            fallback_used=False,
            requires_user_approval=True,
            decision="escalate_to_user",
            reason=risky_reason,
            output_json=output_json,
        )

    if missing_fields:
        return _routed(
            request,
            route,
            confidence=min(requested_confidence, 0.59),
            fallback_used=bool(route.fallback_tier),
            requires_user_approval=route.fallback_tier is None,
            decision="schema_validation_failed",
            reason=f"Missing required output fields: {', '.join(missing_fields)}",
            output_json={**output_json, "missing_fields": missing_fields},
        )

    if requested_confidence >= CONFIDENCE_ACCEPT_THRESHOLD:
        return _routed(
            request,
            route,
            confidence=requested_confidence,
            fallback_used=False,
            requires_user_approval=False,
            decision="accept",
            reason="Confidence meets accept threshold.",
            output_json=output_json,
        )

    if requested_confidence >= CONFIDENCE_VERIFY_THRESHOLD:
        return _routed(
            request,
            route,
            confidence=requested_confidence,
            fallback_used=True,
            requires_user_approval=False,
            decision="verify_with_fallback",
            reason="Confidence is below accept threshold; route should verify with another mock model path.",
            output_json=output_json,
        )

    return _routed(
        request,
        route,
        confidence=requested_confidence,
        fallback_used=bool(route.fallback_tier),
        requires_user_approval=route.fallback_tier is None,
        decision="escalate_low_confidence",
        reason="Confidence is below verification threshold.",
        output_json=output_json,
    )


def default_model_configs() -> list[LLMModelConfigResponse]:
    return [
        LLMModelConfigResponse(
            id=None,
            task_type=route.task_type,
            tier=route.tier,
            provider=route.provider,
            model=route.model,
            priority=route.priority,
            max_input_tokens=route.max_input_tokens,
            max_output_tokens=route.max_output_tokens,
            max_cost_usd=route.max_cost_usd,
            enabled=True,
            fallback_tier=route.fallback_tier,
            schema_version=route.schema_version,
        )
        for route in DEFAULT_TASK_ROUTES.values()
    ]


def _routed(
    request: LLMCompleteRequest,
    route: TaskRoute,
    confidence: float,
    fallback_used: bool,
    requires_user_approval: bool,
    decision: str,
    reason: str,
    output_json: dict[str, Any],
) -> RoutedLLMCall:
    model = route.fallback_model if fallback_used and route.fallback_model else route.model
    tier = route.fallback_tier if fallback_used and route.fallback_tier is not None else route.tier
    return RoutedLLMCall(
        provider=request.provider or route.provider,
        model=request.model or model,
        tier=tier,
        confidence=confidence,
        prompt_version=request.prompt_version or f"{request.task_type}:mock-v1",
        schema_version=request.schema_version or route.schema_version,
        fallback_used=fallback_used,
        requires_user_approval=requires_user_approval,
        decision=decision,
        reason=reason,
        output_json={
            **output_json,
            "confidence": confidence,
            "requires_escalation": requires_user_approval or decision != "accept",
            "routing_decision": decision,
            "reason": reason,
        },
    )


def _mock_output_json(request: LLMCompleteRequest) -> dict[str, Any]:
    return {
        "result": request.input_json or {"text": "Mock LLM response"},
        "task_type": request.task_type,
        "mock_mode": True,
    }


def _missing_required_fields(output_json: dict[str, Any], required_fields: list[str]) -> list[str]:
    result = output_json.get("result")
    if not isinstance(result, dict):
        return required_fields
    return [field for field in required_fields if field not in result]


def _risky_reason(request: LLMCompleteRequest) -> str | None:
    haystack = f"{request.task_type} {request.prompt}".lower()
    matched_terms = sorted(term for term in RISKY_TERMS if term in haystack)
    if not matched_terms:
        return None
    return f"Task mentions risky terms requiring user approval: {', '.join(matched_terms)}"


def _mock_confidence_for_task(task_type: str) -> float:
    if task_type in {"important_email_review", "final_report_generation"}:
        return 0.88
    if task_type in {"supplier_trust_scoring", "browser_action_decision"}:
        return 0.78
    return 0.95
