from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.scraping import ScrapeSupplierRequest, ScrapeSupplierResponse, SupplierSourceResponse
from app.services.scraping import list_supplier_sources, scrape_supplier_website


router = APIRouter(tags=["suppliers"])


@router.get("/projects/{project_id}/suppliers")
def list_project_suppliers(project_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="list_project_suppliers",
        mock_mode=get_settings().mock_mode,
        project_id=project_id,
    )


@router.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="get_supplier",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )


@router.get("/suppliers/{supplier_id}/sources", response_model=list[SupplierSourceResponse])
def get_supplier_sources(supplier_id: int, db: Session = Depends(get_db)) -> list[SupplierSourceResponse]:
    return list_supplier_sources(db, supplier_id)


@router.post("/suppliers/{supplier_id}/scrape", response_model=ScrapeSupplierResponse)
def scrape_supplier(
    supplier_id: int,
    request: ScrapeSupplierRequest | None = None,
    db: Session = Depends(get_db),
) -> ScrapeSupplierResponse:
    return scrape_supplier_website(db, supplier_id=supplier_id, requested_url=request.url if request else None)


@router.patch("/suppliers/{supplier_id}")
def update_supplier(supplier_id: str) -> dict[str, Any]:
    return placeholder_response(
        area="suppliers",
        action="update_supplier",
        mock_mode=get_settings().mock_mode,
        supplier_id=supplier_id,
    )
