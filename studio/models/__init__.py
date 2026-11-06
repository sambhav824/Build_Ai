"""
studio.models
=============
Intermediate Architectural Representation for BuildSmart 3D Studio.
Shared Pydantic v2 data model bridging CAD/DXF, PDF/raster plans, and 3D geometry.
"""

from studio.models.geometry import (
    Point2D,
    Point3D,
    Vector2D,
    LineSegment2D,
    BoundingBox2D,
)
from studio.models.materials import (
    MaterialCategory,
    MaterialSpec,
    STANDARD_MATERIALS,
)
from studio.models.elements import (
    ElementType,
    ConfidenceLevel,
    WallType,
    DoorType,
    WindowType,
    RoomType,
    StairType,
    Opening,
    Door,
    Window,
    Wall,
    Room,
    Staircase,
    Column,
    Slab,
)
from studio.models.project import (
    FloorLevel,
    Building,
    ArchitecturalProject,
)

__all__ = [
    "Point2D",
    "Point3D",
    "Vector2D",
    "LineSegment2D",
    "BoundingBox2D",
    "MaterialCategory",
    "MaterialSpec",
    "STANDARD_MATERIALS",
    "ElementType",
    "ConfidenceLevel",
    "WallType",
    "DoorType",
    "WindowType",
    "RoomType",
    "StairType",
    "Opening",
    "Door",
    "Window",
    "Wall",
    "Room",
    "Staircase",
    "Column",
    "Slab",
    "FloorLevel",
    "Building",
    "ArchitecturalProject",
]
