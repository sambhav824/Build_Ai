import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Quotation, Design
from database.repositories import ProjectRepository, ApprovalRepository
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects/{project_id}", tags=["Estimation & Quotations"])
orchestrator = Orchestrator()

@router.post("/estimate")
def generate_estimate(project_id: str, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    latest_design = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).first()
    builtup = latest_design.total_builtup_area if latest_design else (proj.plot_area_sqft * 0.75 if proj.plot_area_sqft else 950.0)

    input_payload = {
        "builtup_area_sqft": builtup,
        "floors": proj.floors or 1,
        "client_name": proj.client_name or "Residential Client",
        "project_name": proj.name or f"Project {project_id}"
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="estimation_procurement_agent",
        action="calculate_estimate_and_boq",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        est_res = response.result
        cb = est_res.get("financial_summary", {})
        quotation_rec = Quotation(
            id=f"QUOT-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=est_res.get("version", 1),
            status="DRAFT",
            material_cost=cb.get("material_cost", 0.0),
            labour_cost=cb.get("labour_cost", 0.0),
            transport_cost=cb.get("transport_cost", 0.0),
            equipment_cost=cb.get("equipment_cost", 0.0),
            finishing_cost=cb.get("finishing_labour_cost", 0.0),
            taxes=cb.get("taxes", 0.0),
            contingency=cb.get("contingency", 0.0),
            grand_total=cb.get("grand_total", 0.0),
            boq_items=est_res.get("boq", []),
            assumptions=est_res.get("assumptions", []),
            pdf_report_path=est_res.get("quotation_pdf")
        )
        db.add(quotation_rec)
        proj.status = "ESTIMATE_PROPOSED"
        db.commit()

    return response

@router.get("/boq")
def get_boq(project_id: str, db: Session = Depends(get_db)):
    quotation = db.query(Quotation).filter(Quotation.project_id == project_id).order_by(Quotation.version.desc()).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="No estimate/BOQ found for project")
    return {
        "project_id": project_id,
        "quotation_id": quotation.id,
        "version": quotation.version,
        "grand_total": quotation.grand_total,
        "boq_items": quotation.boq_items,
        "pdf_download_url": f"/api/projects/{project_id}/reports/quotation-pdf"
    }

@router.post("/quotation/approve")
def approve_quotation(project_id: str, db: Session = Depends(get_db)):
    quotation = db.query(Quotation).filter(Quotation.project_id == project_id).order_by(Quotation.version.desc()).first()
    if not quotation:
        raise HTTPException(status_code=404, detail="No quotation found to approve")

    quotation.status = "APPROVED"
    ApprovalRepository.record_approval(
        db=db,
        project_id=project_id,
        item_type="QUOTATION",
        item_version=quotation.version,
        approved_by="Client Commercial Representative",
        status="APPROVED",
        comments=f"Quotation grand total of INR {quotation.grand_total:,.2f} approved for procurement planning."
    )
    db.commit()
    return {"status": "success", "message": f"Quotation v{quotation.version} approved successfully"}
