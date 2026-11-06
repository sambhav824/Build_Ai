"""
studio.recognition.room_extractor
=================================
Room Boundary Polygonization & Semantic Labeling.
Constructs closed room polygons from CAD polylines / intersecting walls,
associates spatial text labels (e.g. "Master Bedroom", "Kitchen", "Bath"),
and determines room types and areas.
"""

from typing import List, Dict, Any, Optional, Tuple
from studio.models.geometry import Point2D, polygon_area
from studio.models.elements import Room, RoomType, ConfidenceLevel
from utils.logging_config import logger

ROOM_KEYWORDS: Dict[RoomType, List[str]] = {
    RoomType.MASTER_BEDROOM: ["master bedroom", "m.bed", "m. bedroom", "master bed", "mbr"],
    RoomType.BEDROOM: ["bedroom", "bed room", "bed", "chambre"],
    RoomType.LIVING: ["living", "hall", "living room", "lounge", "salon", "drawing"],
    RoomType.KITCHEN: ["kitchen", "cuisine", "kit", "cooking"],
    RoomType.DINING: ["dining", "dinning", "dining room", "salle a manger"],
    RoomType.BATHROOM: ["bath", "toilet", "wc", "powder", "restroom", "salle de bain", "washroom"],
    RoomType.BALCONY: ["balcony", "terrace", "deck", "verandah", "porch"],
    RoomType.STAIRWELL: ["stair", "stairs", "staircase", "escalier"],
    RoomType.OFFICE: ["office", "study", "bureau", "work"],
    RoomType.PARKING: ["parking", "garage", "car porch"],
    RoomType.UTILITY: ["utility", "store", "laundry", "wash"],
}


class RoomExtractor:
    """
    Extracts room spaces from closed polygons and attaches spatial textual annotations.
    """

    @staticmethod
    def classify_room_name(text: str) -> Tuple[RoomType, str]:
        """Classify room type and clean name from text label."""
        clean = text.lower().strip()
        for r_type, keywords in ROOM_KEYWORDS.items():
            for kw in keywords:
                if kw in clean:
                    # Return formatted title
                    return r_type, text.strip().title()
        return RoomType.GENERIC, text.strip().title() if text.strip() else "Room"

    @staticmethod
    def _point_in_polygon(pt: Point2D, poly: List[Point2D]) -> bool:
        """Ray-casting algorithm to test if point is inside polygon."""
        n = len(poly)
        if n < 3:
            return False
        inside = False
        p1 = poly[0]
        for i in range(1, n + 1):
            p2 = poly[i % n]
            if pt.y > min(p1.y, p2.y):
                if pt.y <= max(p1.y, p2.y):
                    if pt.x <= max(p1.x, p2.x):
                        if p1.y != p2.y:
                            xinters = (pt.y - p1.y) * (p2.x - p1.x) / (p2.y - p1.y) + p1.x
                        if p1.x == p2.x or pt.x <= xinters:
                            inside = not inside
            p1 = p2
        return inside

    def from_cad_polylines_and_text(
        self,
        polylines: List[Dict[str, Any]],
        texts: List[Dict[str, Any]]
    ) -> List[Room]:
        """
        Extract rooms from closed CAD polylines, associating interior text annotations.
        """
        rooms: List[Room] = []
        room_counter = 1

        for poly_data in polylines:
            if not poly_data.get("is_closed", False):
                continue

            pts = [Point2D(x=p["x"], y=p["y"]) for p in poly_data.get("points", [])]
            if len(pts) < 3:
                continue

            area = polygon_area(pts)
            # Architectural room threshold: between 2.0 m² and 250.0 m²
            if not (2.0 <= area <= 250.0):
                continue

            # Search for text annotation located inside this polygon
            room_name = f"Room {room_counter}"
            room_type = RoomType.GENERIC

            for t in texts:
                t_pos = Point2D(x=t["position"]["x"], y=t["position"]["y"])
                if self._point_in_polygon(t_pos, pts):
                    r_type, r_label = self.classify_room_name(t["text"])
                    room_type = r_type
                    room_name = r_label
                    break

            rooms.append(Room(
                room_id=f"ROOM_{room_counter:03d}",
                name=room_name,
                room_type=room_type,
                boundary_polygon=pts,
                confidence=0.92,
                confidence_level=ConfidenceLevel.HIGH
            ))
            room_counter += 1

        logger.info(f"Extracted {len(rooms)} architectural rooms.")
        return rooms
