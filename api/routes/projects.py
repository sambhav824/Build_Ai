import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Project, Design, Quotation, Schedule, SiteObservation, ApprovalRecord, AgentExecution
from database.repositories import ProjectRepository, ApprovalRepository
from api.schemas.project_schemas import CreateProjectRequest, ApprovalActionRequest
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects", tags=["Projects & Orchestrator"])
orchestrator = Orchestrator()

@router.post("", status_code=201)
def create_project(payload: CreateProjectRequest, db: Session = Depends(get_db)):
    # Generate unique ID: BS-1001, BS-1002, etc.
    existing_count = db.query(Project).count()
    project_id = f"BS-{1001 + existing_count}"

    proj = ProjectRepository.create_project(
        db=db,
        project_id=project_id,
        name=payload.name,
        client_name=payload.client_name,
        plot_area_sqft=payload.plot_area_sqft,
        plot_length_ft=payload.plot_length_ft,
        plot_width_ft=payload.plot_width_ft,
        bhk_configuration=payload.bhk_configuration,
        floors=payload.floors,
        budget=payload.budget,
        architectural_style=payload.architectural_style,
        raw_requirements=payload.raw_requirements
    )

    return {
        "status": "success",
        "project_id": proj.id,
        "project": {
            "id": proj.id,
            "name": proj.name,
            "client_name": proj.client_name,
            "status": proj.status,
            "plot_area_sqft": proj.plot_area_sqft,
            "bhk_configuration": proj.bhk_configuration,
            "budget": proj.budget,
            "created_at": proj.created_at.isoformat() if proj.created_at else None
        }
    }

@router.get("")
def list_projects(db: Session = Depends(get_db)):
    projects = ProjectRepository.list_projects(db)
    return {
        "total": len(projects),
        "projects": [
            {
                "id": p.id,
                "name": p.name,
                "client_name": p.client_name,
                "status": p.status,
                "plot_area_sqft": p.plot_area_sqft,
                "bhk_configuration": p.bhk_configuration,
                "budget": p.budget,
                "created_at": p.created_at.isoformat() if p.created_at else None
            }
            for p in projects
        ]
    }

@router.get("/{project_id}")
def get_project_details(project_id: str, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    designs = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).all()
    quotations = db.query(Quotation).filter(Quotation.project_id == project_id).order_by(Quotation.version.desc()).all()
    schedules = db.query(Schedule).filter(Schedule.project_id == project_id).order_by(Schedule.version.desc()).all()
    observations = db.query(SiteObservation).filter(SiteObservation.project_id == project_id).order_by(SiteObservation.created_at.desc()).all()
    approvals = db.query(ApprovalRecord).filter(ApprovalRecord.project_id == project_id).order_by(ApprovalRecord.timestamp.desc()).all()
    executions = db.query(AgentExecution).filter(AgentExecution.project_id == project_id).order_by(AgentExecution.created_at.desc()).all()

    return {
        "project": {
            "id": proj.id,
            "name": proj.name,
            "client_name": proj.client_name,
            "status": proj.status,
            "plot_area_sqft": proj.plot_area_sqft,
            "plot_length_ft": proj.plot_length_ft,
            "plot_width_ft": proj.plot_width_ft,
            "bhk_configuration": proj.bhk_configuration,
            "floors": proj.floors,
            "budget": proj.budget,
            "architectural_style": proj.architectural_style,
            "raw_requirements": proj.raw_requirements,
            "structured_requirements": proj.structured_requirements,
            "created_at": proj.created_at.isoformat() if proj.created_at else None
        },
        "latest_design": designs[0].layout_2d if designs else None,
        "latest_quotation": quotations[0].boq_items if quotations else None,
        "latest_schedule": schedules[0].tasks if schedules else None,
        "recent_observations_count": len(observations),
        "approvals": [
            {
                "id": a.id,
                "item_type": a.item_type,
                "version": a.item_version,
                "approved_by": a.approved_by,
                "status": a.status,
                "comments": a.comments,
                "timestamp": a.timestamp.isoformat() if a.timestamp else None
            }
            for a in approvals
        ],
        "agent_executions_count": len(executions)
    }

@router.post("/{project_id}/orchestrate-all")
def orchestrate_end_to_end(project_id: str, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    prompt = proj.raw_requirements or f"Construct {proj.bhk_configuration} on {proj.plot_area_sqft} sq ft plot"
    result = orchestrator.run_full_pipeline_step(db, project_id, prompt)

    # Save to database
    if result.get("status") == "completed":
        # Save design
        d_res = result.get("design", {})
        design_rec = Design(
            id=f"DSGN-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=d_res.get("version", 1),
            layout_2d=d_res.get("rooms", []),
            preview_2d_svg=d_res.get("preview_2d_svg"),
            model_3d_file=d_res.get("model_3d_obj"),
            total_builtup_area=d_res.get("total_builtup_sqft", 950.0),
            validation_status=d_res.get("validation")
        )
        db.add(design_rec)

        # Save quotation
        est_res = result.get("estimation", {})
        cb = est_res.get("financial_summary", {})
        quote_rec = Quotation(
            id=f"QUOT-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=est_res.get("version", 1),
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
        db.add(quote_rec)

        # Save schedule
        sc_res = result.get("schedule", {})
        sched_rec = Schedule(
            id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=sc_res.get("version", 1),
            start_date=sc_res.get("start_date", "2026-12-01"),
            estimated_end_date=sc_res.get("estimated_completion_date", "2027-05-01"),
            critical_path=sc_res.get("critical_path_tasks", []),
            tasks=sc_res.get("tasks", [])
        )
        db.add(sched_rec)

        proj.status = "FULL_WORKFLOW_ORCHESTRATED"
        db.commit()

    return result

@router.post("/{project_id}/approvals")
def record_project_approval(project_id: str, payload: ApprovalActionRequest, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    rec = ApprovalRepository.record_approval(
        db=db,
        project_id=project_id,
        item_type=payload.item_type,
        item_version=payload.item_version,
        approved_by=payload.approved_by,
        status=payload.status,
        comments=payload.comments
    )

    return {"status": "success", "approval_id": rec.id, "item_type": rec.item_type, "approval_status": rec.status}
