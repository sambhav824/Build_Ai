import json
import os
from datetime import datetime
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from api.schemas.protocol import AgentRequest, AgentResponse
from engines.scheduling_engine import SchedulingEngine
from utils.logging_config import logger

class SchedulingAgent(BaseAgent):
    """
    Agent 4: Construction Scheduling Agent.
    Generates realistic construction schedules using the Critical Path Method (CPM),
    task dependency graphs, resource availability, and procurement milestones.
    """
    def __init__(self):
        super().__init__(name="scheduling_agent")

    def process(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"SchedulingAgent processing action '{request.action}' for project {request.project_id}")
        inp = request.input

        start_date = inp.get("start_date", datetime.now().strftime("%Y-%m-%d"))
        builtup_sqft = float(inp.get("builtup_area_sqft", 950.0))
        floors = int(inp.get("floors", 1))

        # 1. Deterministic CPM Scheduling Calculation
        schedule_data = SchedulingEngine.calculate_cpm_schedule(
            start_date_str=start_date,
            builtup_sqft=builtup_sqft,
            floors=floors
        )

        # 2. Material Procurement Cross-Dependencies
        # Concrete & Steel must be delivered prior to foundation casting
        procurement_dependencies = [
            {"activity_id": "ACT-03", "material": "Cement & Reinforcement Steel", "required_by": schedule_data["tasks"][2]["start_date"]},
            {"activity_id": "ACT-06", "material": "Bricks & Mortar Sand", "required_by": schedule_data["tasks"][5]["start_date"]},
            {"activity_id": "ACT-09", "material": "Vitrified Floor Tiles", "required_by": schedule_data["tasks"][8]["start_date"]},
        ]

        # 3. Weather Risk Analysis (Monsoon Advisory)
        warnings = []
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            # If construction spans June, July, or August
            end_dt = datetime.strptime(schedule_data["estimated_completion_date"], "%Y-%m-%d")
            # Check month overlap
            monsoon_overlap = any(m in [6, 7, 8] for m in range(start_dt.month, min(13, end_dt.month + (12 if end_dt.year > start_dt.year else 0))))
            if monsoon_overlap:
                warnings.append("Monsoon seasonal precipitation overlap detected (June-August). Ensure site drainage and plinth backfill protection.")
        except Exception:
            pass

        warnings.append("Schedule timeline is deterministic baseline. Site weather and material delivery delays must be monitored by site supervisor.")

        result_payload = {
            "project_id": request.project_id,
            "version": inp.get("version", 1),
            "start_date": schedule_data["start_date"],
            "estimated_completion_date": schedule_data["estimated_completion_date"],
            "total_duration_days": schedule_data["total_duration_calendar_days"],
            "critical_path_tasks": schedule_data["critical_path_tasks"],
            "tasks": schedule_data["tasks"],
            "procurement_dependencies": procurement_dependencies,
            "schedule_status": "PLANNED_AND_BASELINE_ESTABLISHED"
        }

        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="completed",
            result=result_payload,
            warnings=warnings,
            requires_approval=True # Construction schedules require PM / Builder authorization
        )
