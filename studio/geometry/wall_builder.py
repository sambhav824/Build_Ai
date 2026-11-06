"""
studio.geometry.wall_builder
============================
3D Wall Geometry Generator.
Transforms 2D wall centerlines, thicknesses, and heights into precise 3D meshes.
Handles wall segmentations for door and window openings (sill, lintel, side piers).
"""

import math
from typing import List, Dict, Any, Tuple
from studio.models.elements import Wall, Door, Window
from studio.models.geometry import Point2D


class Wall3DBuilder:
    """
    Constructs 3D mesh representations of architectural walls.
    For Three.js rendering, generates positioned boxes and segmented meshes
    deducting window and door voids.
    """

    @staticmethod
    def build_wall_mesh(wall: Wall, floor_elevation_m: float = 0.0) -> List[Dict[str, Any]]:
        """
        Build 3D mesh components for a wall at a given floor elevation.
        Returns a list of 3D primitive nodes (boxes with position, rotation, dimensions)
        ready for Three.js rendering.
        """
        sx, sy = wall.start.x, wall.start.y
        ex, ey = wall.end.x, wall.end.y
        length = wall.length_m
        thickness = wall.thickness_m
        height = wall.height_m

        if length <= 0.01:
            return []

        # Wall angle in radians in the horizontal X-Z ground plane
        # Note: In Three.js, Y is UP, X is right/east, Z is depth/south
        # In 2D CAD: X is east, Y is north -> Maps to Three.js: X=X, Y=elevation, Z=-Y
        dx = ex - sx
        dy = ey - sy
        angle = math.atan2(dy, dx)

        # Midpoint of wall
        mid_x = (sx + ex) / 2.0
        mid_y = (sy + ey) / 2.0

        meshes = []

        # If wall has no openings, return single solid rectangular prism
        if not wall.openings:
            meshes.append({
                "mesh_id": f"{wall.wall_id}_solid",
                "element_id": wall.wall_id,
                "category": "Wall",
                "name": f"Wall ({wall.wall_type.value})",
                "wall_type": wall.wall_type.value,
                "position": [round(mid_x, 4), round(floor_elevation_m + height / 2.0, 4), round(-mid_y, 4)],
                "rotation": [0.0, round(-angle, 4), 0.0],
                "dimensions": [round(length, 4), round(height, 4), round(thickness, 4)],
                "material_id": wall.material_id,
                "is_structural": wall.is_structural,
            })
            return meshes

        # If openings exist, segment wall into pier blocks, sills, and lintels
        # Sort openings by offset along wall
        sorted_openings = sorted(wall.openings, key=lambda op: op.offset_along_wall_m)
        curr_offset = 0.0

        # Cosine and sine for along-wall direction
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        pier_idx = 1
        for op in sorted_openings:
            op_start = max(0.0, op.offset_along_wall_m - op.width_m / 2.0)
            op_end = min(length, op.offset_along_wall_m + op.width_m / 2.0)

            # Left pier
            if op_start > curr_offset:
                pier_len = op_start - curr_offset
                pier_center_dist = curr_offset + pier_len / 2.0
                px = sx + pier_center_dist * cos_a
                py = sy + pier_center_dist * sin_a

                meshes.append({
                    "mesh_id": f"{wall.wall_id}_pier_{pier_idx}",
                    "element_id": wall.wall_id,
                    "category": "Wall",
                    "name": f"Wall Pier {pier_idx}",
                    "wall_type": wall.wall_type.value,
                    "position": [round(px, 4), round(floor_elevation_m + height / 2.0, 4), round(-py, 4)],
                    "rotation": [0.0, round(-angle, 4), 0.0],
                    "dimensions": [round(pier_len, 4), round(height, 4), round(thickness, 4)],
                    "material_id": wall.material_id,
                })
                pier_idx += 1

            # Lintel above opening
            op_top = op.sill_height_m + op.height_m
            if op_top < height:
                lintel_h = height - op_top
                lintel_w = op_end - op_start
                op_center_dist = (op_start + op_end) / 2.0
                lx = sx + op_center_dist * cos_a
                ly = sy + op_center_dist * sin_a
                lintel_elev = floor_elevation_m + op_top + lintel_h / 2.0

                meshes.append({
                    "mesh_id": f"{wall.wall_id}_lintel_{pier_idx}",
                    "element_id": wall.wall_id,
                    "category": "Wall",
                    "name": f"Wall Lintel",
                    "wall_type": wall.wall_type.value,
                    "position": [round(lx, 4), round(lintel_elev, 4), round(-ly, 4)],
                    "rotation": [0.0, round(-angle, 4), 0.0],
                    "dimensions": [round(lintel_w, 4), round(lintel_h, 4), round(thickness, 4)],
                    "material_id": wall.material_id,
                })

            # Sill below opening (for windows)
            if op.sill_height_m > 0:
                sill_h = op.sill_height_m
                sill_w = op_end - op_start
                op_center_dist = (op_start + op_end) / 2.0
                sill_x = sx + op_center_dist * cos_a
                sill_y = sy + op_center_dist * sin_a
                sill_elev = floor_elevation_m + sill_h / 2.0

                meshes.append({
                    "mesh_id": f"{wall.wall_id}_sill_{pier_idx}",
                    "element_id": wall.wall_id,
                    "category": "Wall",
                    "name": f"Wall Sill",
                    "wall_type": wall.wall_type.value,
                    "position": [round(sill_x, 4), round(sill_elev, 4), round(-sill_y, 4)],
                    "rotation": [0.0, round(-angle, 4), 0.0],
                    "dimensions": [round(sill_w, 4), round(sill_h, 4), round(thickness, 4)],
                    "material_id": wall.material_id,
                })

            curr_offset = op_end

        # Right end pier
        if curr_offset < length:
            pier_len = length - curr_offset
            pier_center_dist = curr_offset + pier_len / 2.0
            px = sx + pier_center_dist * cos_a
            py = sy + pier_center_dist * sin_a

            meshes.append({
                "mesh_id": f"{wall.wall_id}_pier_{pier_idx}",
                "element_id": wall.wall_id,
                "category": "Wall",
                "name": f"Wall Pier {pier_idx}",
                "wall_type": wall.wall_type.value,
                "position": [round(px, 4), round(floor_elevation_m + height / 2.0, 4), round(-py, 4)],
                "rotation": [0.0, round(-angle, 4), 0.0],
                "dimensions": [round(pier_len, 4), round(height, 4), round(thickness, 4)],
                "material_id": wall.material_id,
            })

        return meshes
