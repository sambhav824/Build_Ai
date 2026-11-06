"""
studio.geometry.opening_builder
===============================
3D Door & Window Geometry Synthesizer.
Constructs 3D door frames, wood panels, window mullions, and glass glazing.
"""

import math
from typing import List, Dict, Any, Optional
from studio.models.elements import Wall, Door, Window


class Opening3DBuilder:
    """
    Constructs 3D elements for doors and windows.
    """

    @staticmethod
    def build_door_mesh(door: Door, wall: Wall, floor_elevation_m: float = 0.0) -> List[Dict[str, Any]]:
        """
        Build 3D mesh components for a door (frame and wood leaf panel).
        """
        sx, sy = wall.start.x, wall.start.y
        ex, ey = wall.end.x, wall.end.y
        dx = ex - sx
        dy = ey - sy
        angle = math.atan2(dy, dx)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        # Center position of door along wall
        cx = sx + door.offset_along_wall_m * cos_a
        cy = sy + door.offset_along_wall_m * sin_a
        elev = floor_elevation_m + door.height_m / 2.0

        door_type_val = getattr(door, "door_type", "SINGLE_SWING")
        if hasattr(door_type_val, "value"):
            door_type_val = door_type_val.value
        frame_depth = getattr(door, "frame_depth_m", 0.10)
        mat_id = getattr(door, "material_id", "MAT-WOOD-01")

        meshes = []

        # Door frame
        meshes.append({
            "mesh_id": f"{door.opening_id}_frame",
            "element_id": door.opening_id,
            "category": "Door",
            "name": f"Door Frame ({door_type_val})",
            "position": [round(cx, 4), round(elev, 4), round(-cy, 4)],
            "rotation": [0.0, round(-angle, 4), 0.0],
            "dimensions": [round(door.width_m, 4), round(door.height_m, 4), round(frame_depth, 4)],
            "material_id": mat_id,
        })

        return meshes

    @staticmethod
    def build_window_mesh(win: Window, wall: Wall, floor_elevation_m: float = 0.0) -> List[Dict[str, Any]]:
        """
        Build 3D mesh components for a window (aluminum frame and transparent glass pane).
        """
        sx, sy = wall.start.x, wall.start.y
        ex, ey = wall.end.x, wall.end.y
        dx = ex - sx
        dy = ey - sy
        angle = math.atan2(dy, dx)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        cx = sx + win.offset_along_wall_m * cos_a
        cy = sy + win.offset_along_wall_m * sin_a
        elev = floor_elevation_m + win.sill_height_m + win.height_m / 2.0

        win_type_val = getattr(win, "window_type", "SLIDING")
        if hasattr(win_type_val, "value"):
            win_type_val = win_type_val.value
        glazing_mat = getattr(win, "glazing_material_id", "MAT-GLAS-01")

        meshes = []

        # Glass glazing pane
        meshes.append({
            "mesh_id": f"{win.opening_id}_glass",
            "element_id": win.opening_id,
            "category": "Window",
            "name": f"Window Glazing ({win_type_val})",
            "position": [round(cx, 4), round(elev, 4), round(-cy, 4)],
            "rotation": [0.0, round(-angle, 4), 0.0],
            "dimensions": [round(win.width_m, 4), round(win.height_m, 4), 0.04],
            "material_id": glazing_mat,
            "is_transparent": True,
            "opacity": 0.35,
        })

        return meshes
