"""
studio.models.materials
=======================
Material definitions and standard architectural PBR material presets
for 3D visualization, BIM metadata, and indicative cost estimation.
"""

from enum import Enum
from typing import Dict
from pydantic import BaseModel, Field


class MaterialCategory(str, Enum):
    STRUCTURAL = "STRUCTURAL"
    WALL_FINISH = "WALL_FINISH"
    FLOORING = "FLOORING"
    GLAZING = "GLAZING"
    WOOD = "WOOD"
    METAL = "METAL"
    CUSTOM = "CUSTOM"


class MaterialSpec(BaseModel):
    """Architectural material specification with PBR rendering parameters."""
    material_id: str = Field(..., description="Unique identifier (e.g., MAT-CONC-01)")
    name: str = Field(..., description="Human-readable name")
    category: MaterialCategory
    color_hex: str = Field("#CCCCCC", description="Hex color code (e.g., #E5A83B)")
    opacity: float = Field(1.0, ge=0.0, le=1.0, description="Transparency (1.0 = solid)")
    roughness: float = Field(0.6, ge=0.0, le=1.0, description="PBR roughness for Three.js")
    metalness: float = Field(0.1, ge=0.0, le=1.0, description="PBR metalness for Three.js")
    density_kg_m3: float = Field(2400.0, description="Material density for weight estimation")
    unit_cost_inr: float = Field(0.0, description="Indicative cost per sq.m or cu.m")
    is_transparent: bool = Field(False, description="Whether rendering requires transparency flag")


# ---------------------------------------------------------------------------
# Standard Architectural Presets Library
# ---------------------------------------------------------------------------

STANDARD_MATERIALS: Dict[str, MaterialSpec] = {
    "MAT-CONC-01": MaterialSpec(
        material_id="MAT-CONC-01",
        name="Cast-in-place Concrete",
        category=MaterialCategory.STRUCTURAL,
        color_hex="#9CA3AF",
        opacity=1.0,
        roughness=0.85,
        metalness=0.05,
        density_kg_m3=2400.0,
        unit_cost_inr=5500.0
    ),
    "MAT-BRK-01": MaterialSpec(
        material_id="MAT-BRK-01",
        name="Red Clay Brick Masonry",
        category=MaterialCategory.STRUCTURAL,
        color_hex="#B45309",
        opacity=1.0,
        roughness=0.9,
        metalness=0.0,
        density_kg_m3=1800.0,
        unit_cost_inr=9.5
    ),
    "MAT-PLAS-01": MaterialSpec(
        material_id="MAT-PLAS-01",
        name="Sand-Faced Plaster (Desert Sand)",
        category=MaterialCategory.WALL_FINISH,
        color_hex="#D4A853",
        opacity=1.0,
        roughness=0.7,
        metalness=0.05,
        density_kg_m3=1600.0,
        unit_cost_inr=450.0
    ),
    "MAT-PLAS-02": MaterialSpec(
        material_id="MAT-PLAS-02",
        name="Smooth Interior Plaster (Warm Alabaster)",
        category=MaterialCategory.WALL_FINISH,
        color_hex="#FAF6EE",
        opacity=1.0,
        roughness=0.5,
        metalness=0.0,
        density_kg_m3=1400.0,
        unit_cost_inr=320.0
    ),
    "MAT-GLAS-01": MaterialSpec(
        material_id="MAT-GLAS-01",
        name="Clear Architectural Float Glass",
        category=MaterialCategory.GLAZING,
        color_hex="#93C5FD",
        opacity=0.35,
        roughness=0.1,
        metalness=0.9,
        density_kg_m3=2500.0,
        unit_cost_inr=1450.0,
        is_transparent=True
    ),
    "MAT-WOOD-01": MaterialSpec(
        material_id="MAT-WOOD-01",
        name="Engineered Teak / Hardwood",
        category=MaterialCategory.WOOD,
        color_hex="#78350F",
        opacity=1.0,
        roughness=0.4,
        metalness=0.0,
        density_kg_m3=750.0,
        unit_cost_inr=3200.0
    ),
    "MAT-STL-01": MaterialSpec(
        material_id="MAT-STL-01",
        name="Structural Steel / Frame Profile",
        category=MaterialCategory.METAL,
        color_hex="#374151",
        opacity=1.0,
        roughness=0.3,
        metalness=0.85,
        density_kg_m3=7850.0,
        unit_cost_inr=75.0
    ),
    "MAT-TILE-01": MaterialSpec(
        material_id="MAT-TILE-01",
        name="Vitrified Matte Ceramic Tiles",
        category=MaterialCategory.FLOORING,
        color_hex="#E5E7EB",
        opacity=1.0,
        roughness=0.35,
        metalness=0.1,
        density_kg_m3=2200.0,
        unit_cost_inr=950.0
    ),
    "MAT-TILE-02": MaterialSpec(
        material_id="MAT-TILE-02",
        name="Charcoal Granite Slabs",
        category=MaterialCategory.FLOORING,
        color_hex="#1F2937",
        opacity=1.0,
        roughness=0.25,
        metalness=0.15,
        density_kg_m3=2700.0,
        unit_cost_inr=1800.0
    ),
}


def get_material(material_id: str) -> MaterialSpec:
    """Retrieve material specification by ID with safe fallback."""
    return STANDARD_MATERIALS.get(
        material_id,
        STANDARD_MATERIALS["MAT-PLAS-01"]
    )
