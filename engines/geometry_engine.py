from typing import List, Dict, Any, Tuple
import math

class Rect:
    def __init__(self, x: float, y: float, w: float, h: float, label: str = "", elevation_ft: float = 0.0, floor: int = 0):
        self.x = round(float(x), 2)
        self.y = round(float(y), 2)
        self.w = round(float(w), 2)
        self.h = round(float(h), 2)
        self.label = label
        self.elevation_ft = round(float(elevation_ft), 2)
        self.floor = int(floor)

    @property
    def area(self) -> float:
        return round(self.w * self.h, 2)

    @property
    def right(self) -> float:
        return round(self.x + self.w, 2)

    @property
    def top(self) -> float:
        return round(self.y + self.h, 2)

    def intersects(self, other: 'Rect', tolerance: float = 0.05) -> bool:
        """Checks if two rectangles overlap with an internal area > tolerance."""
        overlap_x = max(0.0, min(self.right, other.right) - max(self.x, other.x))
        overlap_y = max(0.0, min(self.top, other.top) - max(self.y, other.y))
        return (overlap_x * overlap_y) > tolerance

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.label,
            "x": self.x,
            "y": self.y,
            "w": self.w,
            "h": self.h,
            "area_sqft": self.area,
            "elevation_ft": self.elevation_ft,
            "floor": self.floor
        }

class GeometryEngine:
    """
    Deterministic 2D architectural geometry engine.
    Handles coordinate transforms, room positioning, wall generation with thickness,
    and door/window openings without requiring external C++ GEOS dependencies.
    """

    @staticmethod
    def generate_walls_from_rooms(rooms: List[Rect], outer_thickness: float = 0.75, inner_thickness: float = 0.38) -> Dict[str, Any]:
        """
        Derives exterior perimeter bounding walls and interior dividing partition walls.
        """
        if not rooms:
            return {"exterior_walls": [], "interior_walls": []}

        min_x = min(r.x for r in rooms)
        max_x = max(r.right for r in rooms)
        min_y = min(r.y for r in rooms)
        max_y = max(r.top for r in rooms)

        # Exterior envelope segments
        exterior_walls = [
            {"start": [min_x, min_y], "end": [max_x, min_y], "thickness": outer_thickness, "type": "exterior", "side": "south"},
            {"start": [max_x, min_y], "end": [max_x, max_y], "thickness": outer_thickness, "type": "exterior", "side": "east"},
            {"start": [max_x, max_y], "end": [min_x, max_y], "thickness": outer_thickness, "type": "exterior", "side": "north"},
            {"start": [min_x, max_y], "end": [min_x, min_y], "thickness": outer_thickness, "type": "exterior", "side": "west"},
        ]

        # Interior walls derived from room boundaries
        interior_walls = []
        for i in range(len(rooms)):
            r1 = rooms[i]
            for j in range(i + 1, len(rooms)):
                r2 = rooms[j]
                # Vertical common edge
                if abs(r1.right - r2.x) < 0.1 or abs(r2.right - r1.x) < 0.1:
                    y_start = max(r1.y, r2.y)
                    y_end = min(r1.top, r2.top)
                    if y_end - y_start > 1.0: # Minimum wall length 1 ft
                        x_coord = r1.right if abs(r1.right - r2.x) < 0.1 else r2.right
                        interior_walls.append({
                            "start": [round(x_coord, 2), round(y_start, 2)],
                            "end": [round(x_coord, 2), round(y_end, 2)],
                            "thickness": inner_thickness,
                            "type": "interior"
                        })
                # Horizontal common edge
                if abs(r1.top - r2.y) < 0.1 or abs(r2.top - r1.y) < 0.1:
                    x_start = max(r1.x, r2.x)
                    x_end = min(r1.right, r2.right)
                    if x_end - x_start > 1.0:
                        y_coord = r1.top if abs(r1.top - r2.y) < 0.1 else r2.top
                        interior_walls.append({
                            "start": [round(x_start, 2), round(y_coord, 2)],
                            "end": [round(x_end, 2), round(y_coord, 2)],
                            "thickness": inner_thickness,
                            "type": "interior"
                        })

        return {
            "bounding_box": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y, "width": round(max_x - min_x, 2), "height": round(max_y - min_y, 2)},
            "exterior_walls": exterior_walls,
            "interior_walls": interior_walls
        }

    @staticmethod
    def derive_openings(rooms: List[Rect]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Determines standard door and window placements for each room.
        """
        doors = []
        windows = []

        for r in rooms:
            # Door placement: near interior edge
            door_x = round(r.x + min(2.5, r.w * 0.25), 2)
            door_y = round(r.y, 2)
            doors.append({
                "room": r.label,
                "x": door_x,
                "y": door_y,
                "width": 3.0 if "Bathroom" not in r.label else 2.5,
                "swing": "inward_left"
            })

            # Window placement: on external perimeter
            win_x = round(r.x + (r.w / 2.0), 2)
            win_y = round(r.top, 2)
            windows.append({
                "room": r.label,
                "x": win_x,
                "y": win_y,
                "width": 4.0 if "Bathroom" not in r.label else 2.0,
                "type": "sliding"
            })

        return {"doors": doors, "windows": windows}
