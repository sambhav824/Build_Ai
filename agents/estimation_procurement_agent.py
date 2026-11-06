import json
import os
from typing import Dict, Any, List
from agents.base_agent import BaseAgent
from api.schemas.protocol import AgentRequest, AgentResponse
from engines.quantity_calculator import QuantityCalculator
from engines.cost_calculator import CostCalculator
from reports.quotation_generator import QuotationGenerator
from reports.boq_generator import BOQGenerator
from utils.logging_config import logger

class EstimationProcurementAgent(BaseAgent):
    """
    Agent 2: Estimation & Procurement Agent.
    Calculates material requirements using verified engineering formulas,
    checks warehouse inventory, calculates itemized costs, produces PDF/Excel
    quotations, and coordinates supplier procurement.
    """
    def __init__(self):
        super().__init__(name="estimation_procurement_agent")

    def process(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"EstimationProcurementAgent processing {request.action} for {request.project_id}")
        inp = request.input

        # 1. Determine built-up area and parameters
        builtup_sqft = float(inp.get("builtup_area_sqft", 950.0))
        floors = int(inp.get("floors", 1))
        client_name = inp.get("client_name", "Residential Client")
        project_name = inp.get("project_name", f"Project {request.project_id}")

        # 2. Deterministic Civil Engineering Quantity Calculation (IS 1200)
        boq_data = QuantityCalculator.calculate_boq(
            builtup_area_sqft=builtup_sqft,
            floors=floors,
            wall_type=inp.get("wall_type", "brick")
        )

        # 3. Cost Calculation Engine (Itemized Rates, Labor, Contingency, Taxes)
        cost_data = CostCalculator.calculate_cost_estimate(
            boq_items=boq_data["boq_items"],
            builtup_area_sqft=builtup_sqft * floors,
            custom_rates=inp.get("custom_rates")
        )

        # 4. Inventory Comparison & Shortage Detection
        inventory_items = self._load_inventory()
        inventory_map = {item["id"]: item for item in inventory_items}

        shortages = []
        procurement_orders = []

        for item in cost_data["itemized_boq"]:
            code = item["item_code"]
            required_qty = item["quantity"]
            inv_record = inventory_map.get(code)
            available = float(inv_record.get("available_qty", 0.0)) if inv_record else 0.0
            unit_cost = float(inv_record.get("unit_cost", item.get("unit_rate", 0))) if inv_record else item.get("unit_rate", 0)
            supplier = inv_record.get("supplier_name", "Regional Building Supplier") if inv_record else "Pending Supplier Quote"
            lead_time = inv_record.get("lead_time_days", 3) if inv_record else 3

            shortage_qty = max(0.0, round(required_qty - available, 2))

            shortage_entry = {
                "item_code": code,
                "material_name": item["name"],
                "unit": item["unit"],
                "required_qty": required_qty,
                "available_stock": available,
                "shortage_qty": shortage_qty,
                "status": "SUFFICIENT" if shortage_qty == 0 else "DEFICIT_ORDER_REQUIRED"
            }
            shortages.append(shortage_entry)

            if shortage_qty > 0:
                procurement_orders.append({
                    "po_number": f"PO-{request.project_id}-{code}",
                    "material_name": item["name"],
                    "quantity_to_order": shortage_qty,
                    "unit": item["unit"],
                    "recommended_supplier": supplier,
                    "estimated_order_value": round(shortage_qty * unit_cost, 2),
                    "lead_time_days": lead_time,
                    "authorization_required": True
                })

        # 5. Generate Professional PDF Quotation & Excel BOQ
        pdf_path = None
        excel_path = None
        try:
            pdf_path = QuotationGenerator.generate_pdf(
                project_id=request.project_id,
                client_name=client_name,
                project_name=project_name,
                builtup_area_sqft=builtup_sqft * floors,
                cost_data=cost_data
            )
            excel_path = BOQGenerator.generate_excel(
                project_id=request.project_id,
                project_name=project_name,
                boq_items=cost_data["itemized_boq"]
            )
        except Exception as e:
            logger.error(f"Report generation error: {e}")

        result_payload = {
            "project_id": request.project_id,
            "version": inp.get("version", 1),
            "total_builtup_sqft": builtup_sqft * floors,
            "boq": cost_data["itemized_boq"],
            "assumptions": boq_data["assumptions"],
            "financial_summary": cost_data["cost_breakdown"],
            "inventory_shortages": shortages,
            "procurement_order_recommendations": procurement_orders,
            "quotation_pdf": pdf_path,
            "boq_excel": excel_path,
            "approval_required": True
        }

        warnings = [
            "All estimates are illustrative based on standard engineering indexes.",
            "Actual construction BOQ must be verified by certified structural engineers.",
            "Material procurement must not execute automatically without explicit human authorization."
        ]

        return AgentResponse(
            project_id=request.project_id,
            execution_id=request.execution_id,
            agent=self.name,
            status="completed",
            result=result_payload,
            warnings=warnings,
            requires_approval=True # Quotation requires customer signoff
        )

    def _load_inventory(self) -> List[Dict[str, Any]]:
        inventory_file = "data/inventory.json"
        if os.path.exists(inventory_file):
            try:
                with open(inventory_file, "r", encoding="utf-8") as f:
                    return json.load(f).get("inventory", [])
            except Exception:
                pass
        return []
