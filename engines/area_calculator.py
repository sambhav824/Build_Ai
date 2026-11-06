from typing import Dict, Any, List

class AreaCalculator:
    """
    Civil Engineering regulatory calculation engine.
    Calculates permissible built-up area, setbacks, FSI/FAR, and ground coverage
    in compliance with standard residential municipal building bylaws.
    """

    @staticmethod
    def calculate_setbacks_and_coverage(plot_area_sqft: float, plot_length_ft: float, plot_width_ft: float) -> Dict[str, Any]:
        """
        Determines statutory setback requirements based on standard plot tiers:
        - Small plot (< 1500 sq ft): Front 5 ft, Rear 3 ft, Sides 3 ft
        - Medium plot (1500 - 3000 sq ft): Front 8 ft, Rear 5 ft, Sides 4 ft
        - Large plot (> 3000 sq ft): Front 10 ft, Rear 7 ft, Sides 5 ft
        """
        if plot_area_sqft <= 1500:
            front_setback = 5.0
            rear_setback = 3.0
            side_setback_left = 3.0
            side_setback_right = 3.0
            max_coverage_ratio = 0.75 # 75% max ground coverage
            permissible_fsi = 1.75
        elif plot_area_sqft <= 3000:
            front_setback = 8.0
            rear_setback = 5.0
            side_setback_left = 4.0
            side_setback_right = 4.0
            max_coverage_ratio = 0.65
            permissible_fsi = 2.0
        else:
            front_setback = 10.0
            rear_setback = 7.0
            side_setback_left = 5.0
            side_setback_right = 5.0
            max_coverage_ratio = 0.55
            permissible_fsi = 2.25

        buildable_length = max(10.0, plot_length_ft - (front_setback + rear_setback))
        buildable_width = max(10.0, plot_width_ft - (side_setback_left + side_setback_right))
        buildable_footprint_sqft = round(buildable_length * buildable_width, 2)
        max_ground_coverage_sqft = round(plot_area_sqft * max_coverage_ratio, 2)

        actual_permissible_ground_footprint = min(buildable_footprint_sqft, max_ground_coverage_sqft)
        max_total_builtup_sqft = round(plot_area_sqft * permissible_fsi, 2)

        return {
            "plot_area_sqft": plot_area_sqft,
            "plot_length_ft": plot_length_ft,
            "plot_width_ft": plot_width_ft,
            "setbacks": {
                "front_ft": front_setback,
                "rear_ft": rear_setback,
                "side_left_ft": side_setback_left,
                "side_right_ft": side_setback_right
            },
            "buildable_length_ft": round(buildable_length, 2),
            "buildable_width_ft": round(buildable_width, 2),
            "max_ground_coverage_ratio": max_coverage_ratio,
            "max_ground_coverage_sqft": max_ground_coverage_sqft,
            "actual_permissible_footprint_sqft": actual_permissible_ground_footprint,
            "permissible_fsi": permissible_fsi,
            "max_total_builtup_sqft": max_total_builtup_sqft,
            "regulatory_reference": "Model Building Bye-Laws (Residential Plotted Housing) - Guidelines only. Subject to Municipal Corporation verification."
        }

    @staticmethod
    def validate_room_fit(rooms: List[Dict[str, Any]], permissible_footprint_sqft: float, floors: int = 1) -> Dict[str, Any]:
        """
        Validates that the sum of required carpet areas + ~10% circulation fits within permissible footprint.
        Multi-floor buildings allocate rooms across the available total permissible footprint.
        """
        total_carpet = sum(r.get("min_sqft", 0) for r in rooms)
        circulation_allowance = round(total_carpet * 0.08, 2) # Efficient residential circulation factor ~8%
        total_estimated_builtup = round(total_carpet + circulation_allowance, 2)

        available_capacity = round(permissible_footprint_sqft * floors, 2)
        is_valid = total_estimated_builtup <= available_capacity
        margin_sqft = round(available_capacity - total_estimated_builtup, 2)

        return {
            "total_carpet_sqft": total_carpet,
            "circulation_sqft": circulation_allowance,
            "estimated_builtup_sqft": total_estimated_builtup,
            "permissible_capacity_sqft": available_capacity,
            "is_valid": is_valid,
            "margin_sqft": margin_sqft,
            "status": "APPROVED" if is_valid else "WARNING_OVERSIZE"
        }
