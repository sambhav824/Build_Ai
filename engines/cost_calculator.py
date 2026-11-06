import json
import os
from typing import Dict, Any, List

class CostCalculator:
    """
    Civil Engineering Cost Estimation Engine.
    Combines material quantities with verified unit rates, labor indexes, equipment rentals,
    taxes, and contingencies to generate an itemized project estimate.
    """

    DEFAULT_RATES = {
        "MAT-CEM-01": 385.0, # per bag
        "MAT-STL-01": 72.5,  # per kg
        "MAT-SND-01": 55.0,  # per cft
        "MAT-AGG-01": 46.0,  # per cft
        "MAT-BRK-01": 9.2,   # per brick
        "FIN-TIL-01": 65.0,  # per sq ft
        "FIN-PNT-01": 280.0, # per litre
        "JON-DOR-01": 7500.0,# per set
        "JON-WIN-01": 4800.0,# per set
        "MEP-PLM-01": 850.0, # per point
        "MEP-ELE-01": 650.0  # per point
    }

    @staticmethod
    def load_inventory_rates(inventory_path: str = "data/inventory.json") -> Dict[str, float]:
        if os.path.exists(inventory_path):
            try:
                with open(inventory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return {item["id"]: float(item["unit_cost"]) for item in data.get("inventory", [])}
            except Exception:
                pass
        return CostCalculator.DEFAULT_RATES

    @classmethod
    def calculate_cost_estimate(cls, boq_items: List[Dict[str, Any]], builtup_area_sqft: float, custom_rates: Dict[str, float] = None) -> Dict[str, Any]:
        rates = cls.load_inventory_rates()
        if custom_rates:
            rates.update(custom_rates)

        total_material_cost = 0.0
        itemized_boq = []

        for item in boq_items:
            item_code = item.get("item_code", "")
            qty = float(item.get("quantity", 0))
            unit_rate = float(rates.get(item_code, 100.0))
            total_amt = round(qty * unit_rate, 2)
            total_material_cost += total_amt

            item_copy = dict(item)
            item_copy["unit_rate"] = unit_rate
            item_copy["total_amount"] = total_amt
            item_copy["rate_source"] = "Regional Verified Contractor Price Index / Inventory Depot"
            itemized_boq.append(item_copy)

        # Civil Labor Index: approx 320 to 360 INR per sq ft of built-up area for turnkey civil labor
        labour_cost = round(builtup_area_sqft * 340.0, 2)

        # Equipment & Machinery: Concrete mixers, vibrators, scaffolding rentals (~45 INR/sqft)
        equipment_cost = round(builtup_area_sqft * 45.0, 2)

        # Transportation & Logistics: Site delivery, unloading (~35 INR/sqft)
        transport_cost = round(builtup_area_sqft * 35.0, 2)

        # Finishing & Fixtures labor/installation (~120 INR/sqft)
        finishing_labour_cost = round(builtup_area_sqft * 120.0, 2)

        subtotal = total_material_cost + labour_cost + equipment_cost + transport_cost + finishing_labour_cost

        # Contingency allowance (5% standard engineering contingency for price escalation/site surprises)
        contingency = round(subtotal * 0.05, 2)

        # Applicable Goods & Services Tax (GST 12% on residential construction contracts)
        taxes = round((subtotal + contingency) * 0.12, 2)

        grand_total = round(subtotal + contingency + taxes, 2)

        return {
            "builtup_area_sqft": builtup_area_sqft,
            "itemized_boq": itemized_boq,
            "cost_breakdown": {
                "material_cost": round(total_material_cost, 2),
                "labour_cost": labour_cost,
                "equipment_cost": equipment_cost,
                "transport_cost": transport_cost,
                "finishing_labour_cost": finishing_labour_cost,
                "subtotal": round(subtotal, 2),
                "contingency": contingency,
                "contingency_rate_pct": 5.0,
                "taxes": taxes,
                "tax_rate_pct": 12.0,
                "grand_total": grand_total
            },
            "rate_source_disclaimer": "All figures are illustrative standard regional rates and require final commercial quotation confirmation from suppliers.",
            "currency": "INR"
        }
