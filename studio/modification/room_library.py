"""
studio.modification.room_library
================================
Configurable Architectural Room Dimension Library.
Maintains SI metric defaults (meters) for rooms, circulation, wall thicknesses,
and inter-story heights according to architectural standards.
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from studio.models.elements import RoomType


class RoomDimensionSpec(BaseModel):
    """Architectural room dimension specification."""
    room_type: str
    display_name: str
    default_width_m: float = Field(..., ge=1.0, le=20.0)
    default_length_m: float = Field(..., ge=1.0, le=20.0)
    min_width_m: float = Field(1.2, ge=0.8)
    min_length_m: float = Field(1.5, ge=0.8)
    min_area_sqm: Optional[float] = None
    default_ceiling_height_m: float = Field(3.0, ge=2.1, le=5.0)
    recommended_doors: int = Field(1, ge=1, le=3)
    recommended_windows: int = Field(1, ge=0, le=4)
    preferred_orientation: str = Field("ANY", description="NORTH, SOUTH, EAST, WEST, CORNER, CENTRAL")

    @property
    def default_area_sqm(self) -> float:
        return round(self.default_width_m * self.default_length_m, 2)

    @property
    def area_sqm(self) -> float:
        return self.default_area_sqm


# Default architectural library specs (SI meters)
DEFAULT_ROOM_LIBRARY: Dict[str, RoomDimensionSpec] = {
    "bedroom": RoomDimensionSpec(
        room_type="bedroom",
        display_name="Bedroom",
        default_width_m=3.6,
        default_length_m=3.6,
        min_width_m=3.0,
        min_length_m=3.0,
        recommended_windows=1,
        preferred_orientation="CORNER"
    ),
    "master_bedroom": RoomDimensionSpec(
        room_type="master_bedroom",
        display_name="Master Bedroom",
        default_width_m=4.5,
        default_length_m=4.0,
        min_width_m=3.6,
        min_length_m=3.6,
        recommended_windows=2,
        preferred_orientation="SOUTH_EAST"
    ),
    "washroom": RoomDimensionSpec(
        room_type="washroom",
        display_name="Washroom",
        default_width_m=1.5,
        default_length_m=2.1,
        min_width_m=1.2,
        min_length_m=1.8,
        recommended_windows=1,
        preferred_orientation="CENTRAL"
    ),
    "attached_bathroom": RoomDimensionSpec(
        room_type="attached_bathroom",
        display_name="Attached Bathroom",
        default_width_m=1.5,
        default_length_m=2.1,
        min_width_m=1.2,
        min_length_m=1.8,
        recommended_windows=1,
        preferred_orientation="ADJACENT"
    ),
    "living_room": RoomDimensionSpec(
        room_type="living_room",
        display_name="Living Room",
        default_width_m=4.5,
        default_length_m=4.0,
        min_width_m=3.6,
        min_length_m=3.6,
        recommended_windows=2,
        preferred_orientation="FRONT"
    ),
    "kitchen": RoomDimensionSpec(
        room_type="kitchen",
        display_name="Kitchen",
        default_width_m=3.0,
        default_length_m=3.0,
        min_width_m=2.4,
        min_length_m=2.4,
        recommended_windows=1,
        preferred_orientation="EAST"
    ),
    "balcony": RoomDimensionSpec(
        room_type="balcony",
        display_name="Balcony / Deck",
        default_width_m=3.0,
        default_length_m=1.5,
        min_width_m=1.2,
        min_length_m=1.0,
        recommended_windows=0,
        preferred_orientation="EXTERIOR"
    ),
    "dining": RoomDimensionSpec(
        room_type="dining",
        display_name="Dining Space",
        default_width_m=3.5,
        default_length_m=3.0,
        min_width_m=2.4,
        min_length_m=2.4,
        recommended_windows=1,
        preferred_orientation="CENTRAL"
    )
}

# Architectural standard building parameters
BUILDING_STANDARDS = {
    "floor_to_floor_height_m": 3.0,
    "internal_wall_thickness_m": 0.15,
    "external_wall_thickness_m": 0.23,
    "slab_thickness_m": 0.15,
    "min_passage_width_m": 1.0,
    "staircase_flight_width_m": 1.0,
    "door_standard_width_m": 0.9,
    "door_standard_height_m": 2.1,
    "washroom_door_width_m": 0.75,
    "window_standard_width_m": 1.2,
    "window_standard_height_m": 1.2,
    "window_sill_height_m": 0.9,
}


class RoomLibrary:
    """Manages configurable room dimensions and building parameters."""

    def __init__(self, custom_specs: Optional[Dict[str, RoomDimensionSpec]] = None):
        self.specs: Dict[str, RoomDimensionSpec] = dict(DEFAULT_ROOM_LIBRARY)
        if custom_specs:
            self.specs.update(custom_specs)
        self.standards: Dict[str, float] = dict(BUILDING_STANDARDS)

    def normalize_room_type(self, raw_type: str) -> str:
        """Normalize natural language room type string."""
        clean = raw_type.lower().strip().replace("-", "_").replace(" ", "_")
        if clean in self.specs:
            return clean
        if "master" in clean:
            return "master_bedroom"
        if "bed" in clean:
            return "bedroom"
        if any(w in clean for w in ["washroom", "bath", "toilet", "wc", "restroom"]):
            return "washroom"
        if "live" in clean or "hall" in clean or "lounge" in clean:
            return "living_room"
        if "kit" in clean or "cook" in clean:
            return "kitchen"
        if "balc" in clean or "terrace" in clean or "deck" in clean:
            return "balcony"
        if "dine" in clean or "dining" in clean:
            return "dining"
        return "bedroom"

    def get_dimension(self, room_type: str) -> RoomDimensionSpec:
        """Get dimension specification for room type."""
        norm = self.normalize_room_type(room_type)
        return self.specs.get(norm, self.specs["bedroom"])

    def register_room_spec(self, spec: RoomDimensionSpec) -> None:
        """Register or override a custom architectural room specification."""
        self.specs[spec.room_type] = spec

    def to_dict(self) -> Dict[str, Any]:
        """Export dictionary representation for UI settings inspection."""
        return {
            "rooms": {k: v.model_dump() for k, v in self.specs.items()},
            "standards": self.standards
        }
