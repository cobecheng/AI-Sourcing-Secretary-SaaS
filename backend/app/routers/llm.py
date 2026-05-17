from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.llm import LLMCompleteRequest, LLMCompleteResponse, LLMBudgetResponse, LLMUsageResponse
from app.services.llm_usage import complete_with_mock_llm, get_project_budget, get_project_usage, get_user_usage


router = APIRouter(prefix="/llm", tags=["llm-router"])


@router.post("/complete", response_model=LLMCompleteResponse)
def complete_with_llm_router(
    request: LLMCompleteRequest,
    db: Session = Depends(get_db),
) -> LLMCompleteResponse:
    return complete_with_mock_llm(db, request)


@router.get("/usage/project/{project_id}", response_model=LLMUsageResponse)
def get_project_llm_usage(project_id: int, db: Session = Depends(get_db)) -> LLMUsageResponse:
    return get_project_usage(db, project_id)


@router.get("/usage/user/{user_id}", response_model=LLMUsageResponse)
def get_user_llm_usage(user_id: int, db: Session = Depends(get_db)) -> LLMUsageResponse:
    return get_user_usage(db, user_id)


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


@router.get("/budgets/project/{project_id}", response_model=LLMBudgetResponse)
def get_project_llm_budget(project_id: int, db: Session = Depends(get_db)) -> LLMBudgetResponse:
    return get_project_budget(db, project_id)


@router.patch("/budgets/project/{project_id}")
def update_project_llm_budget(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="llm-router",
        action="update_project_llm_budget",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )
