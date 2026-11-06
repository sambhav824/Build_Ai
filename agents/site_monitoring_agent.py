import os
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from api.schemas.protocol import AgentRequest, AgentResponse
from vision.worker_detection import WorkerDetector
from vision.ppe_detection import PPEDetector
from engines.progress_analyzer import ProgressAnalyzer
from reports.progress_report import ProgressReportGenerator
from utils.logging_config import logger

class SiteMonitoringAgent(BaseAgent):
    """
    Agent 5: Site Monitoring & Progress Agent.
    Analyzes site imagery using Computer Vision, counts visible workers,
    inspects PPE safety compliance, compares actual site milestones with planned CPM tasks,
    and identifies critical path delays.
    """
    def __init__(self):
        super().__init__(name="site_monitoring_agent")

    def process(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"SiteMonitoringAgent processing '{request.action}' for project {request.project_id}")
        inp = request.input

        # Accept either 'image_path' or 'image_url' key for flexibility
        image_path = inp.get("image_path") or inp.get("image_url", "uploads/site_sample.jpg")
        observed_stage = inp.get("observed_stage", "Structural RCC Columns & Slab")
        planned_tasks = inp.get("planned_tasks", [])
        reported_blockers = inp.get("reported_blockers", [])

        # 1. Computer Vision Worker Detection & Annotation
        worker_res = WorkerDetector.detect_workers(image_path)

        # 2. Safety & PPE Compliance Analysis
        ppe_res = PPEDetector.evaluate_ppe(
            image_path=image_path,
            worker_boxes=worker_res["detections"]
        )

        # 3. Schedule Progress & Delay Analysis
        delay_res = ProgressAnalyzer.compare_planned_vs_actual(
            planned_tasks=planned_tasks,
            observed_stage=observed_stage,
            reported_blockers=reported_blockers
        )

        # 4. Generate Site Intelligence PDF Report
        pdf_path = None
        try:
            vision_combined = {
                "total_workers_detected": worker_res["total_workers_detected"],
                "ppe_compliance_rate_pct": ppe_res["compliance_rate_pct"],
                "safety_alerts": ppe_res["safety_alerts"]
            }
            pdf_path = ProgressReportGenerator.generate_pdf(
                project_id=request.project_id,
                project_name=inp.get("project_name", f"Project {request.project_id}"),
                vision_data=vision_combined,
                progress_data=delay_res
            )
        except Exception as e:
            logger.error(f"Failed to generate site report PDF: {e}")

        result_payload = {
            "project_id": request.project_id,
            "media_url": image_path.replace("\\", "/"),
            "annotated_image": worker_res.get("annotated_image"),
            "workers": {
                "count": worker_res["total_workers_detected"],
                "detections": worker_res["detections"]
            },
            "safety_and_ppe": {
                "helmets_detected": ppe_res["helmets_detected"],
                "vests_detected": ppe_res["vests_detected"],
                "compliance_score_percent": ppe_res["compliance_rate_pct"],
                "safety_alerts": ppe_res["safety_alerts"]
            },
            "delay_analysis": delay_res,
            "site_report_pdf": pdf_path.replace("\\", "/") if pdf_path else None
        }

        warnings = [
            "Worker count reflects detected personnel at capture time and is not an automated measure of labor productivity.",
            "PPE alerts are advisory indicators for on-site safety officers."
        ]
        if delay_res["predicted_critical_path_delay_days"] > 0:
            warnings.append(f"Predicted schedule slippage: {delay_res['predicted_critical_path_delay_days']} days on critical path.")

        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="completed",
            result=result_payload,
            warnings=warnings,
            requires_approval=False
        )
