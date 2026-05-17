from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.research import MockResearchStartResponse, ResearchStatusResponse
from app.schemas.search import SearchSuppliersRequest, SearchSuppliersResponse
from app.services.mock_research import get_mock_research_status, run_mock_research
from app.services.search import search_suppliers


router = APIRouter(prefix="/projects/{project_id}/research", tags=["research"])


@router.post("/start", response_model=MockResearchStartResponse)
def start_research(project_id: int, db: Session = Depends(get_db)) -> MockResearchStartResponse:
    return run_mock_research(db, project_id)


@router.get("/status", response_model=ResearchStatusResponse)
def get_research_status(project_id: int, db: Session = Depends(get_db)) -> ResearchStatusResponse:
    return get_mock_research_status(db, project_id)


@router.post("/search", response_model=SearchSuppliersResponse)
def search_project_suppliers(
    project_id: int,
    request: SearchSuppliersRequest,
    db: Session = Depends(get_db),
) -> SearchSuppliersResponse:
    return search_suppliers(db, project_id=project_id, query=request.query, limit=request.limit)
