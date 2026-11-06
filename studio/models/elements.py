"""
studio.models.elements
======================
Architectural building components: Walls, Doors, Windows, Rooms,
Staircases, Columns, and Slabs with geometric dimensions and confidence scores.
"""

from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

from studio.models.geometry import (
    Point2D,
    LineSegment2D,
    BoundingBox2D,
    polygon_area,
    polygon_perimeter,
)


class ElementType(str, Enum):
    WALL = "WALL"
    DOOR = "DOOR"
    WINDOW = "WINDOW"
    ROOM = "ROOM"
    STAIRCASE = "STAIRCASE"
    COLUMN = "COLUMN"
    SLAB = "SLAB"
    BEAM = "BEAM"


class ConfidenceLevel(str, Enum):
    VERIFIED = "VERIFIED"                 # Human verified or explicit CAD dimension
    HIGH = "HIGH"                         # Clear geometry (confidence >= 0.85)
    NEEDS_REVIEW = "NEEDS_REVIEW"         # Ambiguous or partial contour (0.50 - 0.84)
    LOW = "LOW"                           # Weak heuristic (< 0.50)
    USER_OVERRIDDEN = "USER_OVERRIDDEN"   # Edited by architect / user in Studio


class WallType(str, Enum):
    EXTERIOR = "EXTERIOR"       # Outer perimeter load-bearing wall (typically 0.23m - 0.30m)
    INTERIOR = "INTERIOR"       # Interior partition wall (typically 0.10m - 0.15m)
    PARTITION = "PARTITION"     # Non-structural drywall / half-brick
    BEARING = "BEARING"         # Heavy structural reinforced concrete wall
    CURTAIN = "CURTAIN"         # Glass curtain wall facade


class DoorType(str, Enum):
    SINGLE_SWING = "SINGLE_SWING"
    DOUBLE_SWING = "DOUBLE_SWING"
    SLIDING = "SLIDING"
    BIFOLD = "BIFOLD"
    POCKET = "POCKET"
    OPENING_ONLY = "OPENING_ONLY"


class WindowType(str, Enum):
    CASEMENT = "CASEMENT"
    SLIDING = "SLIDING"
    FIXED = "FIXED"
    PIVOT = "PIVOT"
    LOUVERED = "LOUVERED"


class RoomType(str, Enum):
    LIVING = "LIVING"
    BEDROOM = "BEDROOM"
    MASTER_BEDROOM = "MASTER_BEDROOM"
    KITCHEN = "KITCHEN"
    BATHROOM = "BATHROOM"
    BALCONY = "BALCONY"
    CORRIDOR = "CORRIDOR"
    DINING = "DINING"
    STAIRWELL = "STAIRWELL"
    OFFICE = "OFFICE"
    PARKING = "PARKING"
    UTILITY = "UTILITY"
    GENERIC = "GENERIC"


class StairType(str, Enum):
    STRAIGHT = "STRAIGHT"
    L_SHAPE = "L_SHAPE"
    U_SHAPE = "U_SHAPE"
    SPIRAL = "SPIRAL"


# ---------------------------------------------------------------------------
# Base Openings & Components
# ---------------------------------------------------------------------------

class Opening(BaseModel):
    """An opening penetrated through a wall (doorway, window, passage)."""
    opening_id: str
    element_type: ElementType = ElementType.DOOR
    wall_id: Optional[str] = Field(None, description="ID of host wall")
    offset_along_wall_m: float = Field(0.0, description="Distance from wall start point along centerline")
    width_m: float = Field(0.9, ge=0.3, le=5.0, description="Clear opening width in meters")
    height_m: float = Field(2.1, ge=0.5, le=4.0, description="Opening height in meters")
    sill_height_m: float = Field(0.0, ge=0.0, le=2.5, description="Height from floor to bottom of opening")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    verified: bool = False
    source_layer: Optional[str] = None


class Door(Opening):
    """Architectural door with swing parameters and frame specs."""
    element_type: ElementType = ElementType.DOOR
    door_type: DoorType = DoorType.SINGLE_SWING
    swing_direction: str = Field("INWARD_LEFT", description="INWARD_LEFT, INWARD_RIGHT, OUTWARD_LEFT, OUTWARD_RIGHT")
    frame_depth_m: float = Field(0.10, description="Door frame depth")
    material_id: str = Field("MAT-WOOD-01", description="Leaf material")


class Window(Opening):
    """Architectural window opening with glazing parameters and mullion counts."""
    element_type: ElementType = ElementType.WINDOW
    window_type: WindowType = WindowType.CASEMENT
    sill_height_m: float = Field(0.9, ge=0.0, le=2.5, description="Sill elevation above floor level (default 0.9m)")
    glazing_material_id: str = Field("MAT-GLAS-01", description="Glass material")
    frame_material_id: str = Field("MAT-STL-01", description="Window frame material")
    mullion_count: int = Field(1, ge=0, le=6)


class Wall(BaseModel):
    """Architectural wall segment represented by its centerline, thickness, and height."""
    wall_id: str
    element_type: ElementType = ElementType.WALL
    start: Point2D
    end: Point2D
    thickness_m: float = Field(0.23, ge=0.05, le=1.0, description="Wall thickness (default 0.23m / 9 inches)")
    height_m: float = Field(3.0, ge=1.5, le=8.0, description="Wall height in meters (default 3.0m)")
    wall_type: WallType = WallType.EXTERIOR
    material_id: str = Field("MAT-PLAS-01", description="Exterior wall material")
    interior_material_id: str = Field("MAT-PLAS-02", description="Interior wall finish")
    openings: List[Opening] = Field(default_factory=list, description="Doors and windows in this wall")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    verified: bool = False
    source_layer: Optional[str] = None
    is_structural: bool = True

    @property
    def length_m(self) -> float:
        return round(self.start.distance_to(self.end), 4)

    @property
    def axis_segment(self) -> LineSegment2D:
        return LineSegment2D(start=self.start, end=self.end)

    @property
    def gross_area_sqm(self) -> float:
        """Wall surface area before subtracting openings."""
        return round(self.length_m * self.height_m, 3)

    @property
    def net_area_sqm(self) -> float:
        """Wall surface area after deducting door and window openings."""
        openings_area = sum(op.width_m * op.height_m for op in self.openings)
        return round(max(0.0, self.gross_area_sqm - openings_area), 3)

    @property
    def volume_m3(self) -> float:
        return round(self.net_area_sqm * self.thickness_m, 4)


class Room(BaseModel):
    """Enclosed architectural room with boundary polygon and computed area."""
    room_id: str
    element_type: ElementType = ElementType.ROOM
    name: str = Field("Room", description="Human-friendly label (e.g. Master Bedroom)")
    room_type: RoomType = RoomType.GENERIC
    boundary_polygon: List[Point2D] = Field(default_factory=list, description="Closed 2D polygon vertices")
    floor_material_id: str = Field("MAT-TILE-01", description="Flooring material")
    ceiling_height_m: float = Field(3.0, ge=2.1, le=8.0)
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.HIGH
    verified: bool = False

    @property
    def area_sqm(self) -> float:
        return round(polygon_area(self.boundary_polygon), 3)

    @property
    def area_sqft(self) -> float:
        return round(self.area_sqm * 10.7639, 2)

    @property
    def perimeter_m(self) -> float:
        return round(polygon_perimeter(self.boundary_polygon), 3)

    @property
    def bounding_box(self) -> BoundingBox2D:
        return BoundingBox2D.from_points(self.boundary_polygon)

    @property
    def width_m(self) -> float:
        return round(self.bounding_box.width, 3)

    @property
    def length_m(self) -> float:
        return round(self.bounding_box.height, 3)


class Staircase(BaseModel):
    """Architectural staircase flight connecting building floor levels."""
    stair_id: str
    element_type: ElementType = ElementType.STAIRCASE
    start: Point2D
    end: Point2D
    width_m: float = Field(1.0, ge=0.7, le=3.0, description="Flight clear width")
    total_rise_m: float = Field(3.0, ge=1.0, le=6.0, description="Vertical floor-to-floor rise")
    tread_depth_m: float = Field(0.25, ge=0.20, le=0.35, description="Tread run dimension (m)")
    riser_height_m: float = Field(0.175, ge=0.12, le=0.22, description="Riser rise dimension (m)")
    num_steps: int = Field(17, ge=3, le=40)
    stair_type: StairType = StairType.STRAIGHT
    has_handrail: bool = True
    material_id: str = Field("MAT-CONC-01")
    confidence: float = Field(0.9, ge=0.0, le=1.0)
    verified: bool = False


class Column(BaseModel):
    """Vertical structural reinforced concrete or steel column."""
    column_id: str
    element_type: ElementType = ElementType.COLUMN
    position: Point2D
    width_m: float = Field(0.30, ge=0.15, le=1.5)
    depth_m: float = Field(0.30, ge=0.15, le=1.5)
    height_m: float = Field(3.0, ge=1.5, le=8.0)
    material_id: str = Field("MAT-CONC-01")
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    verified: bool = False


class Slab(BaseModel):
    """Horizontal floor or roof slab."""
    slab_id: str
    element_type: ElementType = ElementType.SLAB
    boundary_polygon: List[Point2D]
    thickness_m: float = Field(0.15, ge=0.08, le=0.50, description="Slab thickness (default 0.15m)")
    elevation_m: float = Field(0.0, description="Bottom elevation relative to project datum")
    material_id: str = Field("MAT-CONC-01")
    confidence: float = Field(1.0, ge=0.0, le=1.0)

    @property
    def area_sqm(self) -> float:
        return round(polygon_area(self.boundary_polygon), 3)

    @property
    def volume_m3(self) -> float:
        return round(self.area_sqm * self.thickness_m, 4)
