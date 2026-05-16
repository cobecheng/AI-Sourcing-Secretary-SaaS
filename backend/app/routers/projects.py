from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import ApprovalRequest, Project, Supplier
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.projects import CreateProjectFromChatRequest, ProjectFromChatResponse, ProjectSummaryResponse
from app.services.project_from_chat import create_project_from_chat


router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("")
def create_project() -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="create_project",
        mock_mode=get_settings().mock_mode,
    )


@router.post("/from-chat", response_model=ProjectFromChatResponse)
def create_project_from_chat_endpoint(
    request: CreateProjectFromChatRequest,
    db: Session = Depends(get_db),
) -> ProjectFromChatResponse:
    return create_project_from_chat(db, request)


@router.get("", response_model=list[ProjectSummaryResponse])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectSummaryResponse]:
    supplier_counts = dict(
        db.execute(
            select(Supplier.project_id, func.count(Supplier.id))
            .group_by(Supplier.project_id)
        ).all()
    )
    approval_counts = dict(
        db.execute(
            select(ApprovalRequest.project_id, func.count(ApprovalRequest.id))
            .where(ApprovalRequest.status == "pending")
            .group_by(ApprovalRequest.project_id)
        ).all()
    )

    projects = db.scalars(select(Project).order_by(Project.created_at.desc(), Project.id.desc())).all()
    return [
        ProjectSummaryResponse(
            id=project.id,
            name=project.name,
            status=project.status,
            supplier_count=supplier_counts.get(project.id, 0),
            pending_approvals=approval_counts.get(project.id, 0),
            unread_replies=0,
        )
        for project in projects
    ]


@router.get("/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="get_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.patch("/{project_id}")
def update_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="update_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.delete("/{project_id}")
def delete_project(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="projects",
        action="delete_project",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )
