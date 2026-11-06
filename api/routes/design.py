import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Design
from database.repositories import ProjectRepository, ApprovalRepository
from api.schemas.project_schemas import DesignReviseRequest
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects/{project_id}/design", tags=["Residential Design Studio"])
orchestrator = Orchestrator()

@router.post("/generate")
def generate_design(project_id: str, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    input_payload = {
        "plot": {
            "length_ft": proj.plot_length_ft or 40.0,
            "width_ft": proj.plot_width_ft or 30.0,
            "area_sqft": proj.plot_area_sqft or 1200.0
        },
        "bhk_configuration": proj.bhk_configuration or "2BHK",
        "architectural_style": proj.architectural_style or "Modern",
        "floors": proj.floors or 1
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="design_agent",
        action="generate_layout",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        d_res = response.result
        design_rec = Design(
            id=f"DSGN-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=d_res.get("version", 1),
            status="PROPOSED",
            layout_2d=d_res.get("rooms", []),
            preview_2d_svg=d_res.get("preview_2d_svg"),
            model_3d_file=d_res.get("model_3d_obj"),
            total_builtup_area=d_res.get("total_builtup_sqft", 950.0),
            validation_status=d_res.get("validation")
        )
        db.add(design_rec)
        proj.status = "DESIGN_PROPOSED"
        db.commit()

    return response

@router.get("")
def get_latest_design(project_id: str, db: Session = Depends(get_db)):
    design = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).first()
    if not design:
        raise HTTPException(status_code=404, detail="No design found for project")
    return design

@router.post("/revise")
def revise_design(project_id: str, payload: DesignReviseRequest, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    latest_design = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).first()
    existing_rooms = latest_design.layout_2d if latest_design else []
    current_ver = latest_design.version if latest_design else 1

    input_payload = {
        "plot": {"length_ft": proj.plot_length_ft or 40.0, "width_ft": proj.plot_width_ft or 30.0},
        "revision_prompt": payload.revision_prompt,
        "rooms": existing_rooms,
        "version": current_ver
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="design_agent",
        action="revise_design",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        d_res = response.result
        new_design_rec = Design(
            id=f"DSGN-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=d_res.get("version", current_ver + 1),
            status="REVISED_PENDING_APPROVAL",
            layout_2d=d_res.get("rooms", []),
            preview_2d_svg=d_res.get("preview_2d_svg"),
            model_3d_file=d_res.get("model_3d_obj"),
            total_builtup_area=d_res.get("total_builtup_sqft", 950.0),
            validation_status=d_res.get("validation")
        )
        db.add(new_design_rec)
        db.commit()

    return response

@router.post("/approve")
def approve_design(project_id: str, db: Session = Depends(get_db)):
    latest = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No design found to approve")

    latest.status = "APPROVED"
    ApprovalRepository.record_approval(
        db=db,
        project_id=project_id,
        item_type="DESIGN",
        item_version=latest.version,
        approved_by="Client / Project Manager",
        status="APPROVED",
        comments="Architectural floor plan layout and dimensions approved by customer."
    )
    db.commit()
    return {"status": "success", "message": f"Design v{latest.version} approved successfully"}
