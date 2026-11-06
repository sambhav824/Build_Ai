import os
import cv2
import numpy as np
import pytest
from vision.worker_detection import WorkerDetector
from vision.ppe_detection import PPEDetector
from engines.progress_analyzer import ProgressAnalyzer
from agents.site_monitoring_agent import SiteMonitoringAgent
from api.schemas.protocol import AgentRequest

@pytest.fixture(scope="module")
def sample_site_image(tmp_path_factory):
    img_dir = tmp_path_factory.mktemp("site_images")
    img_path = os.path.join(str(img_dir), "synthetic_site.jpg")

    # Generate synthetic construction site frame (sand, concrete pillars, workers)
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (200, 220, 240) # Sky

    # Ground
    cv2.rectangle(img, (0, 240), (640, 480), (120, 160, 180), -1)
    # Concrete slab / column
    cv2.rectangle(img, (100, 150), (160, 400), (150, 150, 150), -1)
    cv2.rectangle(img, (480, 150), (540, 400), (150, 150, 150), -1)

    cv2.imwrite(img_path, img)
    return img_path

def test_worker_and_ppe_detection(sample_site_image):
    worker_res = WorkerDetector.detect_workers(sample_site_image)
    assert worker_res["total_workers_detected"] > 0
    assert os.path.exists(worker_res["annotated_image"])

    ppe_res = PPEDetector.evaluate_ppe(sample_site_image, worker_res["detections"])
    assert "compliance_rate_pct" in ppe_res
    assert ppe_res["compliance_rate_pct"] > 0

def test_progress_analyzer_delay():
    planned_tasks = [
        {"name": "Site Survey", "start_date": "2026-11-01", "end_date": "2026-11-07"},
        {"name": "Excavation", "start_date": "2026-11-08", "end_date": "2026-11-18"},
        {"name": "Foundation", "start_date": "2026-11-19", "end_date": "2026-12-05"},
        {"name": "Structural RCC Columns & Slab", "start_date": "2026-12-06", "end_date": "2026-12-30"},
    ]

    analysis = ProgressAnalyzer.compare_planned_vs_actual(
        planned_tasks=planned_tasks,
        observed_stage="Foundation", # 1 stage behind Structural
        current_date_str="2026-12-10",
        reported_blockers=["Cement shipment delayed due to interstate permit"]
    )

    assert analysis["visually_observed_stage"] == "Foundation"
    assert analysis["observed_delay_days"] > 0
    assert analysis["reported_delay_days"] == 3
    assert analysis["predicted_critical_path_delay_days"] > 0

def test_site_monitoring_agent_end_to_end(sample_site_image):
    agent = SiteMonitoringAgent()
    req = AgentRequest(
        project_id="BS-SITE-001",
        execution_id="EXEC-SIT-01",
        agent="site_monitoring_agent",
        action="monitor_site_progress",
        input={
            "image_path": sample_site_image,
            "observed_stage": "Structural RCC Columns & Slab",
            "reported_blockers": ["Rain delay during footing excavation"]
        }
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert "workers" in resp.result
    assert "safety_and_ppe" in resp.result
    assert "delay_analysis" in resp.result
    assert resp.result["site_report_pdf"] is not None
    assert os.path.exists(resp.result["site_report_pdf"])
