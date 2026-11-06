"""
studio.recognition.opening_detector
===================================
Door and Window Opening Recognition.
Identifies door swings (CAD arcs, door blocks) and window openings,
maps them to host walls, and computes opening offsets and dimensions.
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from studio.models.geometry import Point2D, LineSegment2D
from studio.models.elements import Wall, Door, Window, DoorType, WindowType, ElementType, ConfidenceLevel
from utils.logging_config import logger


class OpeningDetector:
    """
    Detects door and window openings and embeds them into host walls.
    """

    def __init__(self, default_door_height_m: float = 2.1, default_window_height_m: float = 1.2):
        self.default_door_height_m = default_door_height_m
        self.default_window_height_m = default_window_height_m

    @staticmethod
    def _project_point_on_segment(pt: Point2D, seg: LineSegment2D) -> Tuple[Point2D, float, float]:
        """
        Projects point onto line segment.
        Returns: (projected_point, offset_distance_from_start, perpendicular_distance).
        """
        dx, dy = seg.end.x - seg.start.x, seg.end.y - seg.start.y
        L2 = dx * dx + dy * dy
        if L2 == 0:
            return seg.start, 0.0, pt.distance_to(seg.start)

        t = max(0.0, min(1.0, ((pt.x - seg.start.x) * dx + (pt.y - seg.start.y) * dy) / L2))
        proj = Point2D(x=round(seg.start.x + t * dx, 4), y=round(seg.start.y + t * dy, 4))
        offset = round(t * math.sqrt(L2), 4)
        perp_dist = round(pt.distance_to(proj), 4)
        return proj, offset, perp_dist

    def detect_doors_from_arcs(self, arcs: List[Dict[str, Any]], walls: List[Wall]) -> List[Door]:
        """
        Convert door swing arcs into Door models and associate with closest host wall.
        Arc radius represents door leaf width (typically 0.75m - 1.20m).
        """
        doors: List[Door] = []
        door_counter = 1

        for arc in arcs:
            radius = arc.get("radius_m", 0.9)
            if not (0.60 <= radius <= 1.50):
                continue

            center = Point2D(x=arc["center"]["x"], y=arc["center"]["y"])
            best_wall: Optional[Wall] = None
            best_offset: float = 0.0
            best_dist = float("inf")

            for wall in walls:
                seg = wall.axis_segment
                _, offset, dist = self._project_point_on_segment(center, seg)
                # Door hinge must be within reasonable distance of wall (e.g. <= 0.5m)
                if dist <= 0.50 and dist < best_dist:
                    best_dist = dist
                    best_wall = wall
                    best_offset = offset

            door = Door(
                opening_id=f"DOOR_{door_counter:03d}",
                element_type=ElementType.DOOR,
                door_type=DoorType.SINGLE_SWING,
                wall_id=best_wall.wall_id if best_wall else None,
                offset_along_wall_m=best_offset,
                width_m=round(radius, 2),
                height_m=self.default_door_height_m,
                sill_height_m=0.0,
                confidence=0.92,
                confidence_level=ConfidenceLevel.HIGH,
                source_layer=arc.get("layer")
            )
            doors.append(door)
            door_counter += 1

            if best_wall:
                best_wall.openings.append(door)

        logger.info(f"Detected {len(doors)} doors from swing arcs.")
        return doors

    def detect_windows_from_cad(self, lines: List[Dict[str, Any]], walls: List[Wall]) -> List[Window]:
        """
        Detect window openings from CAD window layers and attach to walls.
        """
        windows: List[Window] = []
        win_lines = [l for l in lines if l.get("category") == "WINDOW" or "win" in l.get("layer", "").lower()]
        win_counter = 1

        for wl in win_lines:
            p1 = Point2D(x=wl["start"]["x"], y=wl["start"]["y"])
            p2 = Point2D(x=wl["end"]["x"], y=wl["end"]["y"])
            width = round(p1.distance_to(p2), 2)
            if not (0.60 <= width <= 3.50):
                continue

            mid = Point2D(x=(p1.x + p2.x) / 2.0, y=(p1.y + p2.y) / 2.0)
            best_wall: Optional[Wall] = None
            best_offset: float = 0.0
            best_dist = float("inf")

            for wall in walls:
                seg = wall.axis_segment
                _, offset, dist = self._project_point_on_segment(mid, seg)
                if dist <= 0.40 and dist < best_dist:
                    best_dist = dist
                    best_wall = wall
                    best_offset = offset

            win = Window(
                opening_id=f"WIN_{win_counter:03d}",
                element_type=ElementType.WINDOW,
                window_type=WindowType.SLIDING,
                wall_id=best_wall.wall_id if best_wall else None,
                offset_along_wall_m=best_offset,
                width_m=width,
                height_m=self.default_window_height_m,
                sill_height_m=0.9,
                confidence=0.90,
                confidence_level=ConfidenceLevel.HIGH,
                source_layer=wl.get("layer")
            )
            windows.append(win)
            win_counter += 1

            if best_wall:
                best_wall.openings.append(win)

        logger.info(f"Detected {len(windows)} windows from CAD lines.")
        return windows
