import os
import uuid
import pytest
from database.connection import init_db, SessionLocal, engine, Base
from database.repositories import ProjectRepository, ApprovalRepository
from database.models import AgentExecution
from agents.orchestrator import Orchestrator

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_project_creation_and_repositories(setup_database):
    db = setup_database
    project_id = "BS-TEST-001"

    # Create project
    proj = ProjectRepository.create_project(
        db=db,
        project_id=project_id,
        name="Modern 2BHK Villa",
        client_name="Test Customer",
        plot_area_sqft=1200.0,
        bhk_configuration="2BHK",
        budget=3500000.0
    )
    assert proj is not None
    assert proj.id == project_id
    assert proj.bhk_configuration == "2BHK"

    # Verify retrieval
    retrieved = ProjectRepository.get_project(db, project_id)
    assert retrieved is not None
    assert retrieved.name == "Modern 2BHK Villa"

def test_orchestrator_routing_all_five_agents(setup_database):
    db = setup_database
    orchestrator = Orchestrator()
    project_id = "BS-TEST-001"

    agents_to_test = [
        ("project_planning_agent", "parse_requirements", {"raw_requirements": "2BHK on 1200 sqft"}),
        ("design_agent", "generate_floorplan", {"plot_area_sqft": 1200, "bhk": "2BHK"}),
        ("estimation_procurement_agent", "estimate_costs", {"builtup_area_sqft": 950}),
        ("scheduling_agent", "create_schedule", {"start_date": "2026-12-01"}),
        ("site_monitoring_agent", "analyze_site_image", {"image_url": "uploads/sample.jpg"}),
    ]

    for agent_name, action, payload in agents_to_test:
        response = orchestrator.route_request(
            db=db,
            agent_name=agent_name,
            action=action,
            project_id=project_id,
            input_payload=payload
        )

        assert response.status == "completed"
        assert response.agent == agent_name
        assert response.project_id == project_id
        assert response.execution_id.startswith("EXEC-")
        assert isinstance(response.result, dict)
        assert len(response.result) > 0

        # Verify execution record persisted in database
        exec_record = db.query(AgentExecution).filter(AgentExecution.id == response.execution_id).first()
        assert exec_record is not None
        assert exec_record.status == "completed"
        assert exec_record.action == action

def test_human_approval_workflow(setup_database):
    db = setup_database
    project_id = "BS-TEST-001"

    # Initially not approved
    assert not ApprovalRepository.check_approval(db, project_id, "DESIGN", 1)

    # Record approval
    app_record = ApprovalRepository.record_approval(
        db=db,
        project_id=project_id,
        item_type="DESIGN",
        item_version=1,
        approved_by="Architect Reviewer",
        status="APPROVED",
        comments="Dimensions and setbacks validated according to local municipal bylaws."
    )
    assert app_record.status == "APPROVED"

    # Now verify approval is active
    assert ApprovalRepository.check_approval(db, project_id, "DESIGN", 1)

def test_loop_prevention(setup_database):
    db = setup_database
    orchestrator = Orchestrator()
    project_id = "BS-TEST-001"

    # Attempt depth beyond threshold
    resp = orchestrator.route_request(
        db=db,
        agent_name="project_planning_agent",
        action="loop_test",
        project_id=project_id,
        input_payload={},
        depth=10
    )
    assert resp.status == "failed"
    assert "Recursion limit exceeded" in resp.error
