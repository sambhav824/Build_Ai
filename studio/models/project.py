"""
studio.models.project
=====================
Hierarchical Architectural Project representation:
ArchitecturalProject -> Building -> FloorLevel -> Components (Walls, Slabs, Openings, Rooms).
Generates BIM element trees matching CAD/BIM software specifications.
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from studio.models.geometry import Point2D, BoundingBox2D
from studio.models.elements import (
    Wall,
    Door,
    Window,
    Room,
    Staircase,
    Column,
    Slab,
)


class DrawingFormat(str, Enum):
    DXF = "DXF"
    DWG = "DWG"
    PDF = "PDF"
    PNG = "PNG"
    JPG = "JPG"
    JPEG = "JPEG"
    SYNTHETIC = "SYNTHETIC"


class MeasurementUnit(str, Enum):
    METERS = "meters"
    MILLIMETERS = "millimeters"
    FEET = "feet"
    INCHES = "inches"


class FloorLevel(BaseModel):
    """An architectural building story / level with distinct elevation and elements."""
    level_id: str = Field(default_factory=lambda: f"lvl_{uuid.uuid4().hex[:6]}")
    name: str = Field("Ground Floor", description="Story name (e.g., Level 01, Level 02)")
    elevation_m: float = Field(0.0, description="Vertical Z elevation from ground datum (meters)")
    floor_to_floor_height_m: float = Field(3.0, ge=2.1, le=8.0, description="Inter-story height")
    default_wall_height_m: float = Field(3.0, ge=1.8, le=8.0)
    slab_thickness_m: float = Field(0.15, ge=0.08, le=0.50)
    is_visible: bool = Field(True, description="Floor visibility toggle")
    opacity: float = Field(1.0, ge=0.0, le=1.0, description="Floor transparency")

    # Contained Architectural Components
    walls: List[Wall] = Field(default_factory=list)
    doors: List[Door] = Field(default_factory=list)
    windows: List[Window] = Field(default_factory=list)
    rooms: List[Room] = Field(default_factory=list)
    stairs: List[Staircase] = Field(default_factory=list)
    columns: List[Column] = Field(default_factory=list)
    slabs: List[Slab] = Field(default_factory=list)

    @property
    def total_builtup_area_sqm(self) -> float:
        """Sum of enclosed room areas on this floor."""
        if self.slabs:
            return round(sum(s.area_sqm for s in self.slabs), 2)
        if self.rooms:
            return round(sum(r.area_sqm for r in self.rooms), 2)
        return 0.0

    @property
    def wall_count(self) -> int:
        return len(self.walls)

    @property
    def door_count(self) -> int:
        return len(self.doors) + sum(len([op for op in w.openings if op.element_type == "DOOR"]) for w in self.walls)

    @property
    def window_count(self) -> int:
        return len(self.windows) + sum(len([op for op in w.openings if op.element_type == "WINDOW"]) for w in self.walls)

    @property
    def room_count(self) -> int:
        return len(self.rooms)

    def get_element_counts(self) -> Dict[str, int]:
        """Return element category counts matching BIM software tree hierarchy."""
        return {
            "Wall": self.wall_count,
            "Door": self.door_count,
            "Window": self.window_count,
            "Room": self.room_count,
            "Column": len(self.columns),
            "Stair": len(self.stairs),
            "Slab": len(self.slabs),
        }


class Building(BaseModel):
    """A collection of vertically stacked building stories / floor levels."""
    building_id: str = Field(default_factory=lambda: f"bld_{uuid.uuid4().hex[:6]}")
    name: str = Field("Residential Building", description="Building block name")
    levels: List[FloorLevel] = Field(default_factory=list)

    @property
    def total_height_m(self) -> float:
        if not self.levels:
            return 0.0
        top = max(lvl.elevation_m + lvl.default_wall_height_m for lvl in self.levels)
        bottom = min(lvl.elevation_m for lvl in self.levels)
        return round(top - bottom, 2)

    @property
    def total_builtup_area_sqm(self) -> float:
        return round(sum(lvl.total_builtup_area_sqm for lvl in self.levels), 2)

    @property
    def total_builtup_area_sqft(self) -> float:
        return round(self.total_builtup_area_sqm * 10.7639, 2)

    @property
    def level_count(self) -> int:
        return len(self.levels)

    def get_all_element_counts(self) -> Dict[str, int]:
        """Aggregate element counts across all floor levels."""
        totals: Dict[str, int] = {
            "Wall": 0, "Door": 0, "Window": 0, "Room": 0,
            "Column": 0, "Stair": 0, "Slab": 0, "Beam": 0
        }
        for lvl in self.levels:
            counts = lvl.get_element_counts()
            for k, v in counts.items():
                totals[k] = totals.get(k, 0) + v
        return totals


class ArchitecturalProject(BaseModel):
    """
    Root Architectural Project Model.
    Unifies CAD entities, OCR extractions, and 3D geometry into one traceable record.
    """
    project_id: str = Field(default_factory=lambda: f"STU-{uuid.uuid4().hex[:8].upper()}")
    project_name: str = Field("Modern 2BHK Architectural Model")
    source_filename: str = Field("drawing.dxf")
    source_format: DrawingFormat = DrawingFormat.DXF
    units: MeasurementUnit = MeasurementUnit.METERS
    scale_factor: float = Field(1.0, description="Scale factor applied to convert drawing units to meters")
    scale_verified: bool = Field(True, description="True if drawing scale was confirmed by user or CAD header")
    pixel_scale_ratio: Optional[float] = Field(None, description="Pixels per meter (for raster drawings)")

    building: Building = Field(default_factory=Building)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_bim_tree_json(self) -> Dict[str, Any]:
        """
        Generate hierarchical BIM element tree JSON matching professional CAD tree view.
        Directly powers the Left Panel in the 3D Studio interface.
        """
        counts = self.building.get_all_element_counts()
        return {
            "project_id": self.project_id,
            "project_name": self.project_name,
            "source_filename": self.source_filename,
            "units": self.units.value,
            "total_builtup_sqm": self.building.total_builtup_area_sqm,
            "total_builtup_sqft": self.building.total_builtup_area_sqft,
            "total_height_m": self.building.total_height_m,
            "levels": [
                {
                    "level_id": lvl.level_id,
                    "name": lvl.name,
                    "elevation_m": lvl.elevation_m,
                    "builtup_sqm": lvl.total_builtup_area_sqm,
                    "is_visible": lvl.is_visible,
                    "element_counts": lvl.get_element_counts(),
                    "rooms": [{"id": r.room_id, "name": r.name, "area_sqm": r.area_sqm} for r in lvl.rooms],
                    "walls_count": lvl.wall_count,
                    "doors_count": lvl.door_count,
                    "windows_count": lvl.window_count,
                }
                for lvl in self.building.levels
            ],
            "building_elements": [
                {"category": "Wall", "count": counts.get("Wall", 0), "icon": "fa-cube"},
                {"category": "Door", "count": counts.get("Door", 0), "icon": "fa-door-open"},
                {"category": "Window", "count": counts.get("Window", 0), "icon": "fa-border-all"},
                {"category": "Room", "count": counts.get("Room", 0), "icon": "fa-vector-square"},
                {"category": "Column", "count": counts.get("Column", 0), "icon": "fa-columns"},
                {"category": "Stair", "count": counts.get("Stair", 0), "icon": "fa-stairs"},
                {"category": "Slab", "count": counts.get("Slab", 0), "icon": "fa-layer-group"},
            ],
            "sections": [
                {"name": "Interior Floor Plan", "type": "PLAN"},
                {"name": "Reflected Ceiling Plan", "type": "CEILING"},
                {"name": "Interior Elevation A-A", "type": "SECTION"},
                {"name": "Building Cross Section B-B", "type": "SECTION"},
            ]
        }
