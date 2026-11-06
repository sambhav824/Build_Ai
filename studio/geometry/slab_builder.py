"""
studio.geometry.slab_builder
============================
3D Horizontal Slab & Ceiling Generator.
Constructs horizontal structural concrete floor and roof slabs
from boundary polygons.
"""

from typing import List, Dict, Any
from studio.models.elements import Slab
from studio.models.geometry import BoundingBox2D


class Slab3DBuilder:
    """
    Builds 3D slabs for floors and ceilings.
    """

    @staticmethod
    def build_slab_mesh(slab: Slab) -> Dict[str, Any]:
        """
        Build 3D mesh representation for a structural slab.
        """
        bbox = BoundingBox2D.from_points(slab.boundary_polygon)
        width = bbox.width
        depth = bbox.height
        thickness = slab.thickness_m
        elev = slab.elevation_m

        mid_x = (bbox.min_x + bbox.max_x) / 2.0
        mid_y = (bbox.min_y + bbox.max_y) / 2.0

        return {
            "mesh_id": f"{slab.slab_id}_mesh",
            "element_id": slab.slab_id,
            "category": "Slab",
            "name": "Structural Floor Slab",
            "position": [round(mid_x, 4), round(elev - thickness / 2.0, 4), round(-mid_y, 4)],
            "rotation": [0.0, 0.0, 0.0],
            "dimensions": [round(width, 4), round(thickness, 4), round(depth, 4)],
            "material_id": slab.material_id,
            "area_sqm": slab.area_sqm,
        }
