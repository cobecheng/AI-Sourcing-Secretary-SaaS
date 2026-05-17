from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.reports import ProjectReportResponse
from app.services.reports import export_project_csv as export_project_csv_service
from app.services.reports import generate_project_report as generate_project_report_service
from app.services.reports import get_project_report as get_project_report_service


router = APIRouter(tags=["reports"])


@router.post("/projects/{project_id}/report/generate", response_model=ProjectReportResponse)
def generate_project_report(project_id: int, db: Session = Depends(get_db)) -> ProjectReportResponse:
    return generate_project_report_service(db, project_id)


@router.get("/projects/{project_id}/report", response_model=ProjectReportResponse)
def get_project_report(project_id: int, db: Session = Depends(get_db)) -> ProjectReportResponse:
    return get_project_report_service(db, project_id)


@router.get("/projects/{project_id}/export.csv")
def export_project_csv(project_id: int, db: Session = Depends(get_db)) -> Response:
    csv_text = export_project_csv_service(db, project_id)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="project-{project_id}-suppliers.csv"'},
    )
