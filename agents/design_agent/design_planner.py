from typing import List, Dict, Any
from engines.geometry_engine import Rect

class DesignPlanner:
    """
    Algorithmic 2D Residential Space Planner.
    Arranges rooms using architectural adjacency rules:
    - Public zone (Living, Dining) near front entrance
    - Service zone (Kitchen, Utility) with morning light / cross-ventilation
    - Private zone (Bedrooms, Attached Baths) secluded at rear
    - Sanitary zone (Common Bath) accessible from common hallway
    """

    @staticmethod
    def generate_layout(
        plot_length_ft: float,
        plot_width_ft: float,
        setbacks: Dict[str, float],
        bhk: str = "2BHK",
        style: str = "Modern"
    ) -> List[Rect]:
        # Derive buildable envelope boundaries
        front_sb = setbacks.get("front_ft", 5.0)
        rear_sb = setbacks.get("rear_ft", 3.0)
        left_sb = setbacks.get("side_left_ft", 3.0)
        right_sb = setbacks.get("side_right_ft", 3.0)

        origin_x = left_sb
        origin_y = front_sb

        b_width = max(20.0, plot_width_ft - (left_sb + right_sb))
        b_length = max(25.0, plot_length_ft - (front_sb + rear_sb))

        rooms: List[Rect] = []

        if bhk.upper() in ["1BHK"]:
            # Single floor 1BHK: Front Living & Kitchen, Rear Bed & Bath
            col1_w = round(b_width * 0.58, 2)
            col2_w = round(b_width - col1_w, 2)

            living_h = round(b_length * 0.52, 2)
            bed_h = round(b_length - living_h, 2)

            rooms.append(Rect(origin_x, origin_y, col1_w, living_h, "Living & Dining"))
            rooms.append(Rect(origin_x + col1_w, origin_y, col2_w, round(living_h * 0.65, 2), "Kitchen"))
            rooms.append(Rect(origin_x + col1_w, origin_y + round(living_h * 0.65, 2), col2_w, round(living_h * 0.35, 2), "Bathroom"))
            rooms.append(Rect(origin_x, origin_y + living_h, col1_w + round(col2_w * 0.4, 2), bed_h, "Master Bedroom"))
            rooms.append(Rect(origin_x + col1_w + round(col2_w * 0.4, 2), origin_y + living_h, round(col2_w * 0.6, 2), bed_h, "Balcony"))

        elif bhk.upper() in ["3BHK", "4BHK"]:
            # 3BHK: 3 Columns / Zones
            c1_w = round(b_width * 0.50, 2)
            c2_w = round(b_width - c1_w, 2)

            r1_h = round(b_length * 0.40, 2)
            r2_h = round(b_length * 0.32, 2)
            r3_h = round(b_length - (r1_h + r2_h), 2)

            # Front Row
            rooms.append(Rect(origin_x, origin_y, c1_w, r1_h, "Living Room"))
            rooms.append(Rect(origin_x + c1_w, origin_y, c2_w, r1_h, "Kitchen & Dining"))

            # Middle Row
            rooms.append(Rect(origin_x, origin_y + r1_h, round(c1_w * 0.7, 2), r2_h, "Bedroom 2"))
            rooms.append(Rect(origin_x + round(c1_w * 0.7, 2), origin_y + r1_h, round(c1_w * 0.3, 2), r2_h, "Common Bath"))
            rooms.append(Rect(origin_x + c1_w, origin_y + r1_h, c2_w, r2_h, "Bedroom 3"))

            # Rear Row
            rooms.append(Rect(origin_x, origin_y + r1_h + r2_h, round(c1_w * 0.75, 2), r3_h, "Master Bedroom"))
            rooms.append(Rect(origin_x + round(c1_w * 0.75, 2), origin_y + r1_h + r2_h, round(c1_w * 0.25, 2), r3_h, "Attached Bath"))
            rooms.append(Rect(origin_x + c1_w, origin_y + r1_h + r2_h, c2_w, r3_h, "Balcony / Deck"))

        else: # Standard 2BHK
            c1_w = round(b_width * 0.55, 2)
            c2_w = round(b_width - c1_w, 2)

            front_h = round(b_length * 0.45, 2)
            rear_h = round(b_length - front_h, 2)

            # Front Zone (Entrance side)
            rooms.append(Rect(origin_x, origin_y, c1_w, front_h, "Living & Dining Room"))
            rooms.append(Rect(origin_x + c1_w, origin_y, c2_w, front_h, "Kitchen"))

            # Rear Zone (Private side)
            bed1_w = round(c1_w * 0.75, 2)
            bath1_w = round(c1_w - bed1_w, 2)
            rooms.append(Rect(origin_x, origin_y + front_h, bed1_w, rear_h, "Master Bedroom"))
            rooms.append(Rect(origin_x + bed1_w, origin_y + front_h, bath1_w, round(rear_h * 0.5, 2), "Attached Bath"))
            rooms.append(Rect(origin_x + bed1_w, origin_y + front_h + round(rear_h * 0.5, 2), bath1_w, round(rear_h * 0.5, 2), "Common Bath"))

            bed2_w = round(c2_w * 0.75, 2)
            balc_w = round(c2_w - bed2_w, 2)
            rooms.append(Rect(origin_x + c1_w, origin_y + front_h, bed2_w, rear_h, "Bedroom 2"))
            rooms.append(Rect(origin_x + c1_w + bed2_w, origin_y + front_h, balc_w, rear_h, "Balcony / Utility"))

        return rooms
