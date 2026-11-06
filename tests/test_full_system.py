"""
test_full_system.py — Full System Integration Test for BuildSmartAI
===================================================================
Tests the complete end-to-end workflow across all 5 AI agents,
API endpoints, database repositories, approvals, and report generations.
"""

import os
import pytest
from database.connection import init_db, SessionLocal, engine, Base
from database.models import Project, Design, Quotation, Schedule, SiteObservation, ApprovalRecord
from api.schemas.project_schemas import (
    CreateProjectRequest,
    PlanRequirementsRequest,
    DesignReviseRequest,
    ScheduleGenerateRequest,
    ApprovalActionRequest,
)
from api.routes import (
    projects,
    planning,
    design,
    estimation,
    procurement,
    scheduling,
    reports,
)
import main


@pytest.fixture(scope="module")
def db_session():
    """Create a fresh database session for the integration test."""
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_health_check():
    """Verify platform health and all 5 registered agents."""
    health = main.health_check()
    assert health["status"] == "healthy"
    assert health["platform"] == "BuildSmartAI"
    assert len(health["agents"]) == 5
    expected_agents = [
        "project_planning_agent",
        "estimation_procurement_agent",
        "design_agent",
        "scheduling_agent",
        "site_monitoring_agent"
    ]
    for ag in expected_agents:
        assert ag in health["agents"]


def test_full_residential_workflow_end_to_end(db_session):
    """
    Simulates the complete client journey:
    1. Project creation
    2. Planning Agent (NLP & zoning)
    3. Design Agent (2D SVG & 3D OBJ generation)
    4. Design Revision (conversational modifier)
    5. Customer Design Approval
    6. Estimation & Procurement Agent (IS 1200 BOQ + PDF Quotation)
    7. Procurement Analysis & PO creation
    8. Quotation Approval
    9. Scheduling Agent (CPM Timeline + Gantt)
    10. Reports verification (PDF & Excel generation)
    11. Full project aggregation check
    12. Central Orchestrator run_full_pipeline_step
    """
    db = db_session

    # -------------------------------------------------------------------
    # Step 1: Create Project
    # -------------------------------------------------------------------
    create_payload = CreateProjectRequest(
        name="End-to-End 2BHK Villa Demo",
        client_name="Mr. Rushikesh K.",
        plot_area_sqft=1200.0,
        plot_length_ft=40.0,
        plot_width_ft=30.0,
        bhk_configuration="2BHK",
        floors=1,
        budget=3500000.0,
        architectural_style="Modern Contemporary",
        raw_requirements=(
            "I want a modern 2BHK house on a 1,200 sq. ft. plot with two bedrooms, "
            "two bathrooms, living room, kitchen, dining space, balcony and parking. "
            "My budget is \u20b935 lakh."
        )
    )
    create_res = projects.create_project(payload=create_payload, db=db)
    assert create_res["status"] == "success"
    pid = create_res["project_id"]
    assert pid.startswith("BS-")

    # -------------------------------------------------------------------
    # Step 2: Planning Agent
    # -------------------------------------------------------------------
    plan_res = planning.run_project_planning(project_id=pid, payload=None, db=db)
    assert plan_res.status == "completed"
    assert plan_res.result["bhk_configuration"] == "2BHK"
    assert len(plan_res.result["rooms"]) >= 6

    # -------------------------------------------------------------------
    # Step 3: Design Agent — Generate 2D Layout & 3D Mesh
    # -------------------------------------------------------------------
    design_res = design.generate_design(project_id=pid, db=db)
    assert design_res.status == "completed"
    assert "preview_2d_svg" in design_res.result
    assert "model_3d_obj" in design_res.result

    # Verify SVG file was written to disk
    svg_path = f"generated_designs/{pid}_floorplan.svg"
    assert os.path.exists(svg_path), f"SVG floorplan missing at {svg_path}"

    # -------------------------------------------------------------------
    # Step 4: Conversational Design Modification
    # -------------------------------------------------------------------
    revise_payload = DesignReviseRequest(
        revision_prompt="Increase the master bedroom size by two feet"
    )
    revise_res = design.revise_design(project_id=pid, payload=revise_payload, db=db)
    assert revise_res.status == "completed"
    assert revise_res.result["version"] == 2

    # -------------------------------------------------------------------
    # Step 5: Customer Design Approval
    # -------------------------------------------------------------------
    approve_dsgn_res = design.approve_design(project_id=pid, db=db)
    assert approve_dsgn_res["status"] == "success"
    assert "approved successfully" in approve_dsgn_res["message"]

    # -------------------------------------------------------------------
    # Step 6: Estimation & Procurement Agent (IS 1200 BOQ & PDF Quotation)
    # -------------------------------------------------------------------
    est_res = estimation.generate_estimate(project_id=pid, db=db)
    assert est_res.status == "completed"
    assert len(est_res.result["boq"]) >= 5
    financial_sum = est_res.result["financial_summary"]
    assert financial_sum["grand_total"] > 1_000_000.0

    # Verify PDF Quotation was generated
    pdf_path = f"generated_reports/Quotation_{pid}.pdf"
    assert os.path.exists(pdf_path), f"Quotation PDF missing at {pdf_path}"

    # -------------------------------------------------------------------
    # Step 7: Get BOQ Summary
    # -------------------------------------------------------------------
    boq_res = estimation.get_boq(project_id=pid, db=db)
    assert boq_res["grand_total"] > 1_000_000.0
    assert len(boq_res["boq_items"]) >= 5

    # -------------------------------------------------------------------
    # Step 8: Procurement — Shortage Analysis & PO Placement
    # -------------------------------------------------------------------
    proc_res = procurement.get_procurement_status(project_id=pid, db=db)
    assert "shortages" in proc_res
    assert "purchase_orders" in proc_res

    po_order_res = procurement.record_purchase_order(
        project_id=pid,
        db=db,
        body={
            "material": "Portland Pozzolana Cement (PPC)",
            "quantity": 100.0,
            "unit": "Bags",
            "supplier": "Ultratech Building Solutions",
            "unit_cost_inr": 380.0,
            "approved_by": "Site Procurement Manager",
            "notes": "Urgent batch for foundation PCC."
        }
    )
    assert po_order_res["status"] == "recorded"
    assert "purchase_order" in po_order_res

    # -------------------------------------------------------------------
    # Step 9: Customer Quotation Approval
    # -------------------------------------------------------------------
    approve_quot_res = estimation.approve_quotation(project_id=pid, db=db)
    assert approve_quot_res["status"] == "success"
    assert "approved successfully" in approve_quot_res["message"]

    # -------------------------------------------------------------------
    # Step 10: Scheduling Agent (CPM Timeline & Gantt)
    # -------------------------------------------------------------------
    sched_payload = ScheduleGenerateRequest(start_date="2026-12-01")
    sched_res = scheduling.generate_schedule(project_id=pid, payload=sched_payload, db=db)
    assert sched_res.status == "completed"
    assert sched_res.result["total_duration_days"] > 100
    assert len(sched_res.result["critical_path_tasks"]) > 0

    # -------------------------------------------------------------------
    # Step 11: Reports Available
    # -------------------------------------------------------------------
    reports_res = reports.list_available_reports(project_id=pid, db=db)
    report_items = reports_res["reports"]
    assert len(report_items) >= 2  # Quotation PDF and Floorplan SVG exist

    # -------------------------------------------------------------------
    # Step 12: Full Project Aggregation Verification
    # -------------------------------------------------------------------
    proj_details = projects.get_project_details(project_id=pid, db=db)
    assert proj_details["project"]["id"] == pid
    assert len(proj_details["approvals"]) >= 2
    assert proj_details["agent_executions_count"] >= 4
    assert proj_details["latest_design"] is not None
    assert proj_details["latest_quotation"] is not None
    assert proj_details["latest_schedule"] is not None

    # -------------------------------------------------------------------
    # Step 13: Central Orchestrator Full Pipeline Run
    # -------------------------------------------------------------------
    orch_res = projects.orchestrate_end_to_end(project_id=pid, db=db)
    assert orch_res["status"] == "completed"
    assert "design" in orch_res
    assert "estimation" in orch_res
    assert "schedule" in orch_res
