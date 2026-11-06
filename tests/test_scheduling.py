import pytest
from engines.scheduling_engine import SchedulingEngine
from agents.scheduling_agent import SchedulingAgent
from api.schemas.protocol import AgentRequest

def test_scheduling_engine_cpm():
    sched = SchedulingEngine.calculate_cpm_schedule(
        start_date_str="2026-12-01",
        builtup_sqft=950.0,
        floors=1
    )

    assert sched is not None
    assert sched["start_date"] == "2026-12-01"
    assert sched["total_duration_calendar_days"] > 100
    assert len(sched["critical_path_tasks"]) > 0

    tasks = {t["id"]: t for t in sched["tasks"]}
    assert "ACT-01" in tasks
    assert "ACT-14" in tasks

    # First task starts at day 0
    assert tasks["ACT-01"]["early_start_day"] == 0
    # Last task finishes at project end
    assert tasks["ACT-14"]["early_finish_day"] == sched["total_duration_calendar_days"]

    # Critical path tasks must have zero slack
    for crit_id in sched["critical_path_tasks"]:
        assert tasks[crit_id]["slack_days"] == 0

def test_scheduling_agent_end_to_end():
    agent = SchedulingAgent()
    req = AgentRequest(
        project_id="BS-SCHED-001",
        execution_id="EXEC-SCH-01",
        agent="scheduling_agent",
        action="generate_baseline_schedule",
        input={
            "start_date": "2026-12-01",
            "builtup_area_sqft": 950.0,
            "floors": 1
        }
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert resp.requires_approval is True
    assert "critical_path_tasks" in resp.result
    assert "procurement_dependencies" in resp.result
    assert len(resp.result["procurement_dependencies"]) >= 3
    assert resp.result["total_duration_days"] > 100
