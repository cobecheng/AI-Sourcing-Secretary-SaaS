from typing import Any

from fastapi import APIRouter

from app.config import get_settings
from app.routers._placeholders import placeholder_response


router = APIRouter(prefix="/llm", tags=["llm-router"])


@router.post("/complete")
def complete_with_llm_router() -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="complete_with_llm_router",
        mock_mode=get_settings().mock_mode,
        safety="business logic must call this internal router, not provider SDKs directly",
    )


@router.get("/usage/project/{project_id}")
def get_project_llm_usage(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="get_project_llm_usage",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/usage/user/{user_id}")
def get_user_llm_usage(user_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="get_user_llm_usage",
        mock_mode=get_settings().mock_mode,
        user_id=user_id,
    )


@router.get("/models")
def list_llm_models() -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="list_llm_models",
        mock_mode=get_settings().mock_mode,
    )


@router.patch("/models/{model_config_id}")
def update_llm_model(model_config_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="update_llm_model",
        mock_mode=get_settings().mock_mode,
        model_config_id=model_config_id,
    )


@router.get("/budgets/project/{project_id}")
def get_project_llm_budget(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="get_project_llm_budget",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.patch("/budgets/project/{project_id}")
def update_project_llm_budget(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="update_project_llm_budget",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )

