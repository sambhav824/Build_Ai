import pytest
from agents.project_planning_agent import ProjectPlanningAgent
from api.schemas.protocol import AgentRequest
from engines.area_calculator import AreaCalculator
from utils.unit_converter import UnitConverter

def test_unit_converter():
    sqft = 1200.0
    sqm = UnitConverter.sqft_to_sqm(sqft)
    assert sqm == 111.48
    back_sqft = UnitConverter.sqm_to_sqft(sqm)
    assert abs(back_sqft - 1200.0) < 1.0

    calc_area, l, w = UnitConverter.compute_plot_dimensions(area_sqft=1200.0, length_ft=40.0)
    assert l == 40.0
    assert w == 30.0
    assert calc_area == 1200.0

def test_area_calculator_zoning():
    zoning = AreaCalculator.calculate_setbacks_and_coverage(plot_area_sqft=1200.0, plot_length_ft=40.0, plot_width_ft=30.0)
    assert zoning["setbacks"]["front_ft"] == 5.0
    assert zoning["setbacks"]["rear_ft"] == 3.0
    assert zoning["max_ground_coverage_ratio"] == 0.75
    assert zoning["actual_permissible_footprint_sqft"] > 500

def test_project_planning_agent_execution():
    agent = ProjectPlanningAgent()
    req = AgentRequest(
        project_id="BS-PLAN-001",
        execution_id="EXEC-PLN-01",
        agent="project_planning_agent",
        action="parse_and_plan",
        input={
            "raw_requirements": "I want a modern 2BHK house with parking and balcony on 1200 sq ft plot. Budget 35 lakh.",
            "plot_length_ft": 40.0,
            "plot_width_ft": 30.0
        }
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert resp.result["bhk_configuration"] == "2BHK"
    assert resp.result["plot"]["area_sqft"] == 1200.0
    assert resp.result["budget"] == 3500000.0
    assert len(resp.result["rooms"]) >= 6
    assert resp.result["preferences"]["parking"] is True
    assert resp.result["preferences"]["balcony"] is True
    assert resp.result["area_validation"]["is_valid"] is True
