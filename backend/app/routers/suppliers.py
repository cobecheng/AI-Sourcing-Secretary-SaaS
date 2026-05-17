from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.routers._placeholders import placeholder_response
from app.schemas.scraping import ScrapeSupplierRequest, ScrapeSupplierResponse, SupplierSourceResponse
from app.schemas.suppliers import ExtractSuppliersRequest, ExtractSuppliersResponse, SupplierResponse
from app.services.scraping import list_supplier_sources, scrape_supplier_website
from app.services.supplier_extraction import (
    extract_suppliers_from_search_results,
    get_supplier as get_supplier_service,
    list_project_suppliers as list_project_suppliers_service,
)


router = APIRouter(tags=["suppliers"])


@router.get("/projects/{project_id}/suppliers", response_model=list[SupplierResponse])
def list_project_suppliers(project_id: int, db: Session = Depends(get_db)) -> list[SupplierResponse]:
    return list_project_suppliers_service(db, project_id)


@router.get("/suppliers/{supplier_id}", response_model=SupplierResponse)
def get_supplier(supplier_id: int, db: Session = Depends(get_db)) -> SupplierResponse:
    return get_supplier_service(db, supplier_id)


@router.post("/projects/{project_id}/suppliers/extract", response_model=ExtractSuppliersResponse)
def extract_project_suppliers(
    project_id: int,
    request: ExtractSuppliersRequest | None = None,
    db: Session = Depends(get_db),
) -> ExtractSuppliersResponse:
    return extract_suppliers_from_search_results(db, project_id, request.results if request else None)


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
