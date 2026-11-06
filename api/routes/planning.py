from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from database.repositories import ProjectRepository
from api.schemas.project_schemas import PlanRequirementsRequest
from agents.orchestrator import Orchestrator

router = APIRouter(prefix="/api/projects/{project_id}", tags=["Project Planning"])
orchestrator = Orchestrator()

@router.post("/plan")
def run_project_planning(project_id: str, payload: PlanRequirementsRequest = None, db: Session = Depends(get_db)):
    proj = ProjectRepository.get_project(db, project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

    input_payload = {
        "raw_requirements": (payload.raw_requirements if payload and payload.raw_requirements else proj.raw_requirements),
        "plot_area_sqft": (payload.plot_area_sqft if payload and payload.plot_area_sqft else proj.plot_area_sqft),
        "plot_length_ft": (payload.plot_length_ft if payload and payload.plot_length_ft else proj.plot_length_ft),
        "plot_width_ft": (payload.plot_width_ft if payload and payload.plot_width_ft else proj.plot_width_ft),
        "bhk_configuration": (payload.bhk_configuration if payload and payload.bhk_configuration else proj.bhk_configuration),
        "floors": (payload.floors if payload and payload.floors else proj.floors),
        "budget": (payload.budget if payload and payload.budget else proj.budget),
        "architectural_style": proj.architectural_style
    }

    response = orchestrator.route_request(
        db=db,
        agent_name="project_planning_agent",
        action="parse_and_plan",
        project_id=project_id,
        input_payload=input_payload
    )

    if response.status == "completed":
        proj.structured_requirements = response.result
        proj.status = "PLAN_READY"
        db.commit()

    return response
