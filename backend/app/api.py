from fastapi import APIRouter

from app.routers import (
    admin,
    approvals,
    chat,
    forms,
    health,
    inbox,
    llm,
    milestones,
    mock,
    outreach,
    projects,
    reports,
    research,
    suppliers,
)


api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(admin.router)
api_router.include_router(mock.router)
api_router.include_router(projects.router)
api_router.include_router(chat.router)
api_router.include_router(milestones.router)
api_router.include_router(research.router)
api_router.include_router(suppliers.router)
api_router.include_router(forms.router)
api_router.include_router(approvals.router)
api_router.include_router(outreach.router)
api_router.include_router(inbox.router)
api_router.include_router(reports.router)
api_router.include_router(llm.router)
