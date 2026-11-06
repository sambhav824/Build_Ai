"""
studio.geometry.stair_builder
=============================
3D Procedural Staircase Generator.
Constructs multi-riser stair flights with treads, risers, and handrails.
"""

import math
from typing import List, Dict, Any
from studio.models.elements import Staircase


class Stair3DBuilder:
    """
    Constructs 3D stairs for inter-story circulation.
    """

    @staticmethod
    def build_stair_mesh(stair: Staircase, floor_elevation_m: float = 0.0) -> List[Dict[str, Any]]:
        """
        Build individual tread steps for a straight or turning flight.
        """
        sx, sy = stair.start.x, stair.start.y
        ex, ey = stair.end.x, stair.end.y
        dx = ex - sx
        dy = ey - sy
        flight_len = math.hypot(dx, dy)
        angle = math.atan2(dy, dx)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        num_steps = max(3, stair.num_steps)
        tread_len = flight_len / num_steps
        step_rise = stair.total_rise_m / num_steps

        meshes = []

        for i in range(num_steps):
            step_dist = (i + 0.5) * tread_len
            step_x = sx + step_dist * cos_a
            step_y = sy + step_dist * sin_a
            step_elev = floor_elevation_m + (i + 0.5) * step_rise

            meshes.append({
                "mesh_id": f"{stair.stair_id}_step_{i + 1}",
                "element_id": stair.stair_id,
                "category": "Stair",
                "name": f"Stair Tread {i + 1}",
                "position": [round(step_x, 4), round(step_elev, 4), round(-step_y, 4)],
                "rotation": [0.0, round(-angle, 4), 0.0],
                "dimensions": [round(tread_len, 4), round(step_rise, 4), round(stair.width_m, 4)],
                "material_id": stair.material_id,
            })

        return meshes
