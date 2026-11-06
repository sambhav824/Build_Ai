from typing import List, Dict, Any
from engines.geometry_engine import Rect

class ConstraintValidator:
    """
    Validates generated architectural layouts against National Building Code (NBC)
    and municipal setback requirements.
    """

    MIN_ROOM_AREAS = {
        "Living": 120.0,
        "Master Bedroom": 110.0,
        "Bedroom": 100.0,
        "Kitchen": 50.0,
        "Bath": 25.0,
        "Balcony": 25.0
    }

    @classmethod
    def validate_layout(
        cls,
        rooms: List[Rect],
        plot_length_ft: float,
        plot_width_ft: float,
        setbacks: Dict[str, float]
    ) -> Dict[str, Any]:
        violations = []
        checks = []

        front_sb = setbacks.get("front_ft", 5.0)
        rear_sb = setbacks.get("rear_ft", 3.0)
        left_sb = setbacks.get("side_left_ft", 3.0)
        right_sb = setbacks.get("side_right_ft", 3.0)

        # 1. Boundary & Setback Clearance Checks
        for r in rooms:
            if r.x < left_sb - 0.05:
                violations.append(f"{r.label} encroaches into left side setback ({r.x:.1f} ft < {left_sb:.1f} ft)")
            if r.right > (plot_width_ft - right_sb + 0.05):
                violations.append(f"{r.label} encroaches into right side setback ({r.right:.1f} ft > {plot_width_ft - right_sb:.1f} ft)")
            if r.y < front_sb - 0.05:
                violations.append(f"{r.label} encroaches into front setback ({r.y:.1f} ft < {front_sb:.1f} ft)")
            if r.top > (plot_length_ft - rear_sb + 0.05):
                violations.append(f"{r.label} encroaches into rear setback ({r.top:.1f} ft > {plot_length_ft - rear_sb:.1f} ft)")

        checks.append({
            "check": "Setback Clearances",
            "passed": len(violations) == 0,
            "details": f"Front: {front_sb}ft, Rear: {rear_sb}ft, Sides: {left_sb}/{right_sb}ft"
        })

        # 2. Minimum Room Area Checks (NBC Standards)
        area_violations = 0
        for r in rooms:
            min_req = 30.0 # Default minimum
            for key, val in cls.MIN_ROOM_AREAS.items():
                if key.lower() in r.label.lower():
                    min_req = val
                    break
            if r.area < min_req:
                violations.append(f"{r.label} area {r.area:.1f} sq ft is below NBC minimum requirement ({min_req} sq ft)")
                area_violations += 1

        checks.append({
            "check": "NBC Minimum Room Area Compliance",
            "passed": area_violations == 0,
            "details": f"Validated {len(rooms)} habitable and utility zones against NBC standards."
        })

        # 3. Non-overlapping Room Check
        overlap_found = False
        for i in range(len(rooms)):
            for j in range(i + 1, len(rooms)):
                if rooms[i].intersects(rooms[j]):
                    violations.append(f"Geometric overlap detected between {rooms[i].label} and {rooms[j].label}")
                    overlap_found = True

        checks.append({
            "check": "Internal Geometric Integrity & Separation",
            "passed": not overlap_found,
            "details": "Ensured clean spatial partition without planar collisions."
        })

        is_approved = len(violations) == 0

        return {
            "is_valid": is_approved,
            "status": "VALIDATED" if is_approved else "VIOLATIONS_DETECTED",
            "checks": checks,
            "violations": violations,
            "disclaimer": "Conceptual geometric validation only. Final structural drawings require certified architect/engineer sign-off."
        }
