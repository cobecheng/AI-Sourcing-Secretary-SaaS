import csv
from io import StringIO
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import AgentRun, Project, ProjectMemory, Supplier, SupplierSource, SupplierTerm
from app.schemas.llm import LLMCompleteRequest
from app.schemas.reports import ProjectReportResponse, SupplierReportItem, SupplierReportTerm
from app.services.llm_router import route_llm_call


REPORT_MEMORY_KEY = "final_supplier_report"


def generate_project_report(db: Session, project_id: int) -> ProjectReportResponse:
    project = _get_project(db, project_id)
    suppliers = _report_suppliers(db, project_id)
    routed = route_llm_call(
        LLMCompleteRequest(
            project_id=project.id,
            task_type="final_report_generation",
            prompt="Generate a concise supplier shortlist report from verified supplier evidence and extracted terms.",
            input_json={"supplier_count": len(suppliers), "suppliers": [item.model_dump() for item in suppliers]},
            required_output_fields=["supplier_count", "suppliers"],
            estimated_cost_usd=0.0,
            actual_cost_usd=0.0,
            input_tokens=320,
            output_tokens=240,
            latency_ms=15,
        )
    )
    agent_run = AgentRun(
        project_id=project.id,
        agent_type="llm_router",
        task_type="final_report_generation",
        status="complete",
        input_json={"supplier_count": len(suppliers), "mock_mode": get_settings().mock_mode},
        output_json={**routed.output_json, "report_supplier_count": len(suppliers)},
        provider=routed.provider,
        model=routed.model,
        input_tokens=320,
        output_tokens=240,
        estimated_cost_usd=0,
        actual_cost_usd=0,
        latency_ms=15,
        prompt_version=routed.prompt_version,
        schema_version=routed.schema_version,
        confidence=routed.confidence,
        fallback_used=routed.fallback_used,
    )
    db.add(agent_run)
    report = _build_report(project.id, suppliers, _routing_payload(routed))
    _store_report(db, project.id, report)
    db.commit()
    return report


def get_project_report(db: Session, project_id: int) -> ProjectReportResponse:
    _get_project(db, project_id)
    memory = db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == REPORT_MEMORY_KEY))
    if memory is None:
        return generate_project_report(db, project_id)
    return ProjectReportResponse(**memory.value)


def export_project_csv(db: Session, project_id: int) -> str:
    _get_project(db, project_id)
    output = StringIO()
    fieldnames = [
        "supplier_id",
        "name",
        "website",
        "status",
        "contact_method",
        "trust_score",
        "relevance_score",
        "moq",
        "price_list_available",
        "payment_terms",
        "shipping_regions",
        "lead_time",
        "account_requirements",
        "source_references",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in _report_suppliers(db, project_id):
        terms = item.terms or SupplierReportTerm()
        writer.writerow(
            {
                "supplier_id": item.supplier_id,
                "name": item.name,
                "website": item.website or "",
                "status": item.status,
                "contact_method": item.contact_method or "",
                "trust_score": item.trust_score if item.trust_score is not None else "",
                "relevance_score": item.relevance_score if item.relevance_score is not None else "",
                "moq": terms.moq or "",
                "price_list_available": "" if terms.price_list_available is None else terms.price_list_available,
                "payment_terms": terms.payment_terms or "",
                "shipping_regions": terms.shipping_regions or "",
                "lead_time": terms.lead_time or "",
                "account_requirements": terms.account_requirements or "",
                "source_references": " | ".join(item.evidence_urls),
            }
        )
    return output.getvalue()


def _get_project(db: Session, project_id: int) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _report_suppliers(db: Session, project_id: int) -> list[SupplierReportItem]:
    suppliers = db.scalars(
        select(Supplier)
        .where(Supplier.project_id == project_id)
        .order_by(Supplier.relevance_score.desc(), Supplier.trust_score.desc(), Supplier.id)
    ).all()
    return [_supplier_report_item(db, supplier) for supplier in suppliers]


def _supplier_report_item(db: Session, supplier: Supplier) -> SupplierReportItem:
    evidence = db.scalars(select(SupplierSource).where(SupplierSource.supplier_id == supplier.id).order_by(SupplierSource.id)).all()
    terms = db.scalar(select(SupplierTerm).where(SupplierTerm.supplier_id == supplier.id).order_by(SupplierTerm.id.desc()))
    evidence_urls = [source.url for source in evidence]
    return SupplierReportItem(
        supplier_id=supplier.id,
        name=supplier.name,
        website=supplier.website,
        status=supplier.status,
        contact_method=supplier.contact_method,
        trust_score=float(supplier.trust_score) if supplier.trust_score is not None else None,
        relevance_score=float(supplier.relevance_score) if supplier.relevance_score is not None else None,
        terms=_terms_response(terms),
        evidence_urls=evidence_urls,
        recommendation=_recommendation(supplier, bool(evidence_urls), terms),
    )


def _terms_response(terms: SupplierTerm | None) -> SupplierReportTerm | None:
    if terms is None:
        return None
    return SupplierReportTerm(
        moq=terms.moq,
        price_list_available=terms.price_list_available,
        payment_terms=terms.payment_terms,
        shipping_regions=terms.shipping_regions,
        lead_time=terms.lead_time,
        account_requirements=terms.account_requirements,
    )


def _recommendation(supplier: Supplier, has_evidence: bool, terms: SupplierTerm | None) -> str:
    if supplier.status == "Manual Review Needed" or not has_evidence:
        return "Manual review before outreach."
    if terms is None:
        return "Good shortlist candidate; terms still need confirmation."
    return "Strong shortlist candidate with captured terms and evidence."


def _build_report(
    project_id: int,
    suppliers: list[SupplierReportItem],
    routing: dict[str, Any],
) -> ProjectReportResponse:
    summary = (
        f"Shortlisted {len(suppliers)} supplier candidate"
        f"{'' if len(suppliers) == 1 else 's'} with evidence references and extracted terms."
    )
    return ProjectReportResponse(
        project_id=project_id,
        mock_mode=get_settings().mock_mode,
        status="generated",
        summary=summary,
        suppliers=suppliers,
        model_routing=routing,
        safety={
            "uses_internal_router": True,
            "premium_report_task": True,
            "requires_api_keys": False,
            "sends_outreach": False,
            "submits_forms": False,
        },
    )


def _store_report(db: Session, project_id: int, report: ProjectReportResponse) -> ProjectMemory:
    memory = db.scalar(select(ProjectMemory).where(ProjectMemory.project_id == project_id, ProjectMemory.key == REPORT_MEMORY_KEY))
    if memory is None:
        memory = ProjectMemory(project_id=project_id, key=REPORT_MEMORY_KEY, value=report.model_dump())
        db.add(memory)
    else:
        memory.value = report.model_dump()
    db.flush()
    return memory


def _routing_payload(routed: Any) -> dict[str, Any]:
    return {
        "provider": routed.provider,
        "model": routed.model,
        "tier": routed.tier,
        "confidence": routed.confidence,
        "fallback_used": routed.fallback_used,
        "requires_user_approval": routed.requires_user_approval,
        "decision": routed.decision,
        "prompt_version": routed.prompt_version,
        "schema_version": routed.schema_version,
    }
