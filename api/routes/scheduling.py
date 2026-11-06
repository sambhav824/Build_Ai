import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import Schedule, Design, Quotation
from database.repositories import ProjectRepository, ApprovalRepository
from api.schemas.project_schemas import ScheduleGenerateRequest
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects/{project_id}/schedule", tags=["Construction Scheduling"])
orchestrator = Orchestrator()

@router.post("")
def generate_schedule(project_id: str, payload: ScheduleGenerateRequest = None, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    latest_design = db.query(Design).filter(Design.project_id == project_id).order_by(Design.version.desc()).first()
    builtup = latest_design.total_builtup_area if latest_design else (proj.plot_area_sqft * 0.75 if proj.plot_area_sqft else 950.0)

    start_date = payload.start_date if payload and payload.start_date else "2026-12-01"

    input_payload = {
        "start_date": start_date,
        "builtup_area_sqft": builtup,
        "floors": proj.floors or 1
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="scheduling_agent",
        action="generate_baseline_schedule",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        s_res = response.result
        sched_rec = Schedule(
            id=f"SCHED-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            version=s_res.get("version", 1),
            status="PLANNED",
            start_date=s_res.get("start_date", start_date),
            estimated_end_date=s_res.get("estimated_completion_date", "2027-05-01"),
            critical_path=s_res.get("critical_path_tasks", []),
            tasks=s_res.get("tasks", [])
        )
        db.add(sched_rec)
        proj.status = "SCHEDULED"
        db.commit()

    return response

@router.get("")
def get_schedule(project_id: str, db: Session = Depends(get_db)):
    sched = db.query(Schedule).filter(Schedule.project_id == project_id).order_by(Schedule.version.desc()).first()
    if not sched:
        raise HTTPException(status_code=404, detail="No schedule found for project")
    return sched
