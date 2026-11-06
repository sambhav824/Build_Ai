import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from database.connection import get_db
from database.models import SiteObservation, Schedule
from database.repositories import ProjectRepository
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects/{project_id}/monitoring", tags=["Site Monitoring & Vision"])
orchestrator = Orchestrator()

@router.post("/upload")
async def upload_site_image(
    project_id: str,
    file: UploadFile = File(...),
    observed_stage: str = Form("Structural RCC Columns & Slab"),
    db: Session = Depends(get_db)
):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{project_id}_{file.filename}"
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    latest_sched = db.query(Schedule).filter(Schedule.project_id == project_id).order_by(Schedule.version.desc()).first()
    planned_tasks = latest_sched.tasks if latest_sched else []

    input_payload = {
        "image_path": file_path,
        "observed_stage": observed_stage,
        "planned_tasks": planned_tasks,
        "project_name": proj.name
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="site_monitoring_agent",
        action="monitor_site_progress",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        res = response.result
        obs = SiteObservation(
            id=f"OBS-{uuid.uuid4().hex[:8].upper()}",
            project_id=project_id,
            media_url=file_path,
            detected_workers=res["workers"]["count"],
            ppe_compliance_rate=res["safety_and_ppe"]["compliance_score_percent"],
            safety_alerts=res["safety_and_ppe"]["safety_alerts"],
            inferred_stage=observed_stage,
            notes=f"Delay status: {res['delay_analysis']['schedule_health']}"
        )
        db.add(obs)
        db.commit()

    return response

@router.get("")
def list_site_observations(project_id: str, db: Session = Depends(get_db)):
    observations = db.query(SiteObservation).filter(SiteObservation.project_id == project_id).order_by(SiteObservation.created_at.desc()).all()
    return {
        "project_id": project_id,
        "total": len(observations),
        "observations": observations
    }

@router.get("/progress")
def get_site_progress_summary(project_id: str, db: Session = Depends(get_db)):
    latest_obs = db.query(SiteObservation).filter(SiteObservation.project_id == project_id).order_by(SiteObservation.created_at.desc()).first()
    return {
        "project_id": project_id,
        "has_observations": latest_obs is not None,
        "latest_observation": latest_obs
    }
