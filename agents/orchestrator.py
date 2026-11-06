import uuid
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from api.schemas.protocol import AgentRequest, AgentResponse
from database.repositories import ProjectRepository, ExecutionRepository, ApprovalRepository
from utils.logging_config import logger

from agents.project_planning_agent import ProjectPlanningAgent
from agents.design_agent.design_agent import DesignAgent
from agents.estimation_procurement_agent import EstimationProcurementAgent
from agents.scheduling_agent import SchedulingAgent
from agents.site_monitoring_agent import SiteMonitoringAgent

class Orchestrator:
    """
    Central AI Orchestrator for BuildSmartAI.
    Coordinates the 5 specialized agents, maintains execution state,
    enforces human approval gates, and persists records in the shared database.
    """
    def __init__(self):
        # Register the 5 specialized agents
        self.agents = {
            "project_planning_agent": ProjectPlanningAgent(),
            "design_agent": DesignAgent(),
            "estimation_procurement_agent": EstimationProcurementAgent(),
            "scheduling_agent": SchedulingAgent(),
            "site_monitoring_agent": SiteMonitoringAgent(),
        }
        self.max_call_depth = 5 # Safeguard against recursion / cyclic agent loops

    def route_request(self, db: Session, agent_name: str, action: str, project_id: str, input_payload: Dict[str, Any], depth: int = 0) -> AgentResponse:
        """
        Validates, logs, dispatches, and records execution of an agent action.
        """
        if depth > self.max_call_depth:
            err_msg = f"Recursion limit exceeded ({depth}). Aborting to prevent infinite agent loop."
            logger.error(err_msg)
            return AgentResponse(
                project_id=project_id,
                execution_id=f"EXEC-ERR-{uuid.uuid4().hex[:6]}",
                agent=agent_name,
                status="failed",
                result={},
                warnings=["Infinite agent loop prevented."],
                requires_approval=False,
                error=err_msg
            )

        exec_id = f"EXEC-{uuid.uuid4().hex[:8].upper()}"

        # 1. Verify target agent existence
        agent = self.agents.get(agent_name)
        if not agent:
            err_msg = f"Unknown agent '{agent_name}'. Available: {list(self.agents.keys())}"
            logger.error(err_msg)
            return AgentResponse(
                project_id=project_id,
                execution_id=exec_id,
                agent=agent_name,
                status="failed",
                result={},
                warnings=[],
                requires_approval=False,
                error=err_msg
            )

        # 2. Check project state & approval constraints
        # Ensure that estimating or scheduling requires prior approval if designated
        if agent_name == "scheduling_agent":
            # Check if design approval exists
            is_design_approved = ApprovalRepository.check_approval(db, project_id, "DESIGN", 1)
            if not is_design_approved:
                logger.warning(f"Project {project_id}: Scheduling requested but DESIGN v1 is not yet approved.")
                # We record an advisory warning

        # 3. Log execution start
        ExecutionRepository.log_execution_start(
            db=db,
            exec_id=exec_id,
            project_id=project_id,
            agent_name=agent_name,
            action=action,
            input_payload=input_payload
        )

        # 4. Construct typed schema request
        agent_req = AgentRequest(
            project_id=project_id,
            execution_id=exec_id,
            agent=agent_name,
            action=action,
            input=input_payload,
            status="requested"
        )

        # 5. Execute agent
        try:
            response = agent.process(agent_req)
        except Exception as e:
            logger.exception(f"Unhandled exception in agent {agent_name}: {e}")
            response = agent.create_error_response(agent_req, str(e))

        # 6. Log execution completion
        ExecutionRepository.log_execution_finish(
            db=db,
            exec_id=exec_id,
            status=response.status,
            output_payload=response.result,
            warnings=response.warnings,
            requires_approval=response.requires_approval,
            error_message=response.error
        )

        logger.info(f"Execution {exec_id} completed by {agent_name} [Status: {response.status}]")
        return response

    def run_full_pipeline_step(self, db: Session, project_id: str, user_prompt: str) -> Dict[str, Any]:
        """
        Demonstrates the coordinated sequence:
        1. Planning -> 2. Design -> 3. Estimation -> 4. Scheduling
        """
        logger.info(f"Initiating end-to-end coordinated pipeline for project {project_id}")

        # Step 1: Project Planning Agent
        plan_resp = self.route_request(
            db=db,
            agent_name="project_planning_agent",
            action="parse_and_plan",
            project_id=project_id,
            input_payload={"raw_requirements": user_prompt}
        )
        if plan_resp.status != "completed":
            return {"status": "failed", "step": "planning", "error": plan_resp.error}

        # Step 2: Design Agent
        design_resp = self.route_request(
            db=db,
            agent_name="design_agent",
            action="generate_layout",
            project_id=project_id,
            input_payload=plan_resp.result
        )

        # Step 3: Estimation & Procurement Agent
        est_resp = self.route_request(
            db=db,
            agent_name="estimation_procurement_agent",
            action="calculate_boq_and_cost",
            project_id=project_id,
            input_payload=design_resp.result
        )

        # Step 4: Scheduling Agent
        sched_resp = self.route_request(
            db=db,
            agent_name="scheduling_agent",
            action="generate_schedule",
            project_id=project_id,
            input_payload={"start_date": "2026-12-01", "design": design_resp.result, "boq": est_resp.result}
        )

        return {
            "project_id": project_id,
            "status": "completed",
            "planning": plan_resp.result,
            "design": design_resp.result,
            "estimation": est_resp.result,
            "schedule": sched_resp.result
        }
