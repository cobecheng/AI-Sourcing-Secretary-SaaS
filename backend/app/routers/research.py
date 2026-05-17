from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import MockResearchStartResponse, ResearchStatusResponse
from app.services.mock_research import get_mock_research_status, run_mock_research


router = APIRouter(prefix="/projects/{project_id}/research", tags=["research"])


@router.post("/start", response_model=MockResearchStartResponse)
def start_research(project_id: int, db: Session = Depends(get_db)) -> MockResearchStartResponse:
    return run_mock_research(db, project_id)


@router.get("/status", response_model=ResearchStatusResponse)
def get_research_status(project_id: int, db: Session = Depends(get_db)) -> ResearchStatusResponse:
    return get_mock_research_status(db, project_id)
