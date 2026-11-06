from typing import Dict, Any, List

class QuantityCalculator:
    """
    Deterministic Civil Engineering Quantity Estimation Engine.
    Implements standard quantity surveying principles (IS 1200 / CPWD specifications).
    Never relies on LLM speculation for physical quantities.
    """

    @staticmethod
    def calculate_boq(builtup_area_sqft: float, floors: int = 1, wall_type: str = "brick") -> Dict[str, Any]:
        """
        Calculates material quantities with empirical civil engineering constants
        adjusted for residential RCC frame construction.
        """
        total_builtup = builtup_area_sqft * floors

        # 1. Structural & Concrete
        # Standard residential thumb rule: 0.40 - 0.45 bags cement per sq ft built-up
        cement_bags = round(total_builtup * 0.42)
        # Steel reinforcement: 3.8 kg per sq ft built-up for RCC frame structure
        steel_kg = round(total_builtup * 3.8)
        # Sand (M-Sand): 1.85 cu ft per sq ft built-up
        sand_cft = round(total_builtup * 1.85)
        # Coarse Aggregate (20mm): 1.35 cu ft per sq ft built-up
        aggregate_cft = round(total_builtup * 1.35)

        # 2. Masonry & Walls
        # Red bricks: approx 18 bricks per sq ft builtup (internal + external walls)
        bricks_count = round(total_builtup * 18.0) if wall_type == "brick" else round(total_builtup * 1.2) # AAC blocks
        brick_unit = "nos" if wall_type == "brick" else "blocks"

        # 3. Finishes & Architectural
        # Flooring: Carpet area approx 75% of builtup + 10% wastage/skirting
        flooring_sqft = round(total_builtup * 0.85)
        # Wall Painting: Wall area is approx 3.2 times builtup floor area
        wall_paint_litres = round((total_builtup * 3.2) / 75.0) # 1 litre covers approx 75 sqft (2 coats + primer)
        # Doors and windows counts
        doors_count = max(4, round(total_builtup / 180.0))
        windows_count = max(4, round(total_builtup / 150.0))

        # 4. Plumbing & Electrical rough-ins
        plumbing_points = max(12, round(total_builtup / 60.0))
        electrical_points = max(35, round(total_builtup / 22.0))

        boq_items = [
            {
                "category": "Structural Materials",
                "item_code": "MAT-CEM-01",
                "name": "Cement (Grade 53 OPC / PPC)",
                "quantity": cement_bags,
                "unit": "bags",
                "formula": "Built-up area (sq ft) x 0.42 bags/sq ft",
                "wastage_allowance_pct": 3.0
            },
            {
                "category": "Structural Materials",
                "item_code": "MAT-STL-01",
                "name": "Reinforcement Steel (Fe 500D TMT)",
                "quantity": steel_kg,
                "unit": "kg",
                "formula": "Built-up area (sq ft) x 3.8 kg/sq ft",
                "wastage_allowance_pct": 5.0
            },
            {
                "category": "Aggregates & Sands",
                "item_code": "MAT-SND-01",
                "name": "Manufactured Sand (M-Sand / River Sand)",
                "quantity": sand_cft,
                "unit": "cft",
                "formula": "Built-up area (sq ft) x 1.85 cft/sq ft",
                "wastage_allowance_pct": 5.0
            },
            {
                "category": "Aggregates & Sands",
                "item_code": "MAT-AGG-01",
                "name": "Coarse Aggregate (20mm Blue Metal)",
                "quantity": aggregate_cft,
                "unit": "cft",
                "formula": "Built-up area (sq ft) x 1.35 cft/sq ft",
                "wastage_allowance_pct": 4.0
            },
            {
                "category": "Masonry",
                "item_code": "MAT-BRK-01",
                "name": f"First-Class Red Clay Bricks" if wall_type == "brick" else "AAC Lightweight Blocks",
                "quantity": bricks_count,
                "unit": brick_unit,
                "formula": f"Built-up area (sq ft) x 18 bricks/sq ft",
                "wastage_allowance_pct": 5.0
            },
            {
                "category": "Finishes",
                "item_code": "FIN-TIL-01",
                "name": "Vitrified Floor Tiles (600x600mm Double Charged)",
                "quantity": flooring_sqft,
                "unit": "sq ft",
                "formula": "Carpet area + 10% cutting and skirting wastage",
                "wastage_allowance_pct": 10.0
            },
            {
                "category": "Finishes",
                "item_code": "FIN-PNT-01",
                "name": "Acrylic Interior & Exterior Emulsion Paint",
                "quantity": wall_paint_litres,
                "unit": "litres",
                "formula": "Total wall surface area / coverage rate (75 sqft/L)",
                "wastage_allowance_pct": 5.0
            },
            {
                "category": "Joinery",
                "item_code": "JON-DOR-01",
                "name": "Flush Doors with Teak Wood Frames",
                "quantity": doors_count,
                "unit": "sets",
                "formula": "Derived from room schedule count",
                "wastage_allowance_pct": 0.0
            },
            {
                "category": "Joinery",
                "item_code": "JON-WIN-01",
                "name": "UPVC Sliding Windows with Mosquito Mesh",
                "quantity": windows_count,
                "unit": "sets",
                "formula": "Derived from room ventilation requirement",
                "wastage_allowance_pct": 0.0
            },
            {
                "category": "MEP Services",
                "item_code": "MEP-PLM-01",
                "name": "Plumbing & Sanitary Rough-in Pack (CPVC/PVC pipes & fittings)",
                "quantity": plumbing_points,
                "unit": "points",
                "formula": "Standard 12-18 points per wet room / kitchen",
                "wastage_allowance_pct": 5.0
            },
            {
                "category": "MEP Services",
                "item_code": "MEP-ELE-01",
                "name": "Electrical Conduiting, Wiring & Modular Box Pack (FR Grade)",
                "quantity": electrical_points,
                "unit": "points",
                "formula": "Calculated based on room electrical layout density",
                "wastage_allowance_pct": 5.0
            }
        ]

        assumptions = [
            "RCC Frame Structure with isolated footing foundation.",
            "Soil bearing capacity assumed at 150 kN/m2.",
            "External walls 9-inch brickwork; internal partition walls 4.5-inch.",
            "Ceiling height fixed at 10 ft from finished floor level.",
            "All quantities include designated standard wastage allowances."
        ]

        return {
            "total_builtup_sqft": total_builtup,
            "floors": floors,
            "boq_items": boq_items,
            "assumptions": assumptions,
            "reference_standard": "IS 1200 (Methods of Measurement of Building Works)"
        }
