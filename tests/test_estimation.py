import os
import pytest
from agents.estimation_procurement_agent import EstimationProcurementAgent
from api.schemas.protocol import AgentRequest
from engines.quantity_calculator import QuantityCalculator
from engines.cost_calculator import CostCalculator

def test_quantity_calculator_boq():
    boq_res = QuantityCalculator.calculate_boq(builtup_area_sqft=950.0, floors=1)
    items = {item["item_code"]: item for item in boq_res["boq_items"]}

    assert "MAT-CEM-01" in items
    assert items["MAT-CEM-01"]["quantity"] == round(950.0 * 0.42) # ~399 bags
    assert "MAT-STL-01" in items
    assert items["MAT-STL-01"]["quantity"] == round(950.0 * 3.8) # ~3610 kg
    assert "MAT-BRK-01" in items
    assert len(boq_res["assumptions"]) > 0

def test_cost_calculator():
    boq_res = QuantityCalculator.calculate_boq(builtup_area_sqft=950.0, floors=1)
    cost_res = CostCalculator.calculate_cost_estimate(boq_items=boq_res["boq_items"], builtup_area_sqft=950.0)

    cb = cost_res["cost_breakdown"]
    assert cb["material_cost"] > 500000.0
    assert cb["labour_cost"] > 250000.0
    assert cb["contingency"] > 0
    assert cb["taxes"] > 0
    assert cb["grand_total"] > cb["subtotal"]

def test_estimation_procurement_agent_end_to_end():
    agent = EstimationProcurementAgent()
    req = AgentRequest(
        project_id="BS-EST-001",
        execution_id="EXEC-EST-01",
        agent="estimation_procurement_agent",
        action="estimate_project",
        input={
            "builtup_area_sqft": 950.0,
            "floors": 1,
            "client_name": "Test Client",
            "project_name": "Test Villa 2BHK"
        }
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert resp.requires_approval is True
    assert "boq" in resp.result
    assert "financial_summary" in resp.result
    assert "inventory_shortages" in resp.result
    assert "procurement_order_recommendations" in resp.result
    
    # Check that PDF and Excel were created
    pdf_path = resp.result.get("quotation_pdf")
    excel_path = resp.result.get("boq_excel")
    assert pdf_path is not None and os.path.exists(pdf_path)
    assert excel_path is not None and os.path.exists(excel_path)
