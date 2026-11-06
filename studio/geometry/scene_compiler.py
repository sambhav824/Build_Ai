"""
studio.geometry.scene_compiler
==============================
Master 3D Scene Compiler & Mesh Exporter.
Transforms the ArchitecturalProject intermediate representation into
an interactive Three.js Scene Graph JSON, with procedural mesh assembly
and multi-format 3D export (OBJ, GLB, STL).
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import trimesh
import numpy as np

from studio.models.project import ArchitecturalProject
from studio.models.materials import STANDARD_MATERIALS
from studio.geometry.wall_builder import Wall3DBuilder
from studio.geometry.slab_builder import Slab3DBuilder
from studio.geometry.opening_builder import Opening3DBuilder
from studio.geometry.stair_builder import Stair3DBuilder
from utils.logging_config import logger


class SceneCompiler:
    """
    Compiles architectural building projects into interactive 3D WebGL scenes
    and exportable 3D CAD meshes.
    """

    @classmethod
    def compile_threejs_scene(cls, project: ArchitecturalProject) -> Dict[str, Any]:
        """
        Compile complete building project into Three.js scene graph JSON.
        Powers the interactive 360° viewport in BuildSmart 3D Studio.
        """
        all_meshes: List[Dict[str, Any]] = []
        materials_dict: Dict[str, Any] = {}

        # Prepare materials map
        for mat_id, mat in STANDARD_MATERIALS.items():
            materials_dict[mat_id] = {
                "name": mat.name,
                "category": mat.category.value,
                "color": mat.color_hex,
                "roughness": mat.roughness,
                "metalness": mat.metalness,
                "opacity": mat.opacity,
                "transparent": mat.opacity < 0.99,
                "wireframe": False,
            }

        # Track 3D bounding box
        min_x, min_y, min_z = float("inf"), float("inf"), float("inf")
        max_x, max_y, max_z = float("-inf"), float("-inf"), float("-inf")

        def update_bounds(pos: List[float], dims: List[float]):
            nonlocal min_x, min_y, min_z, max_x, max_y, max_z
            px, py, pz = pos
            dx, dy, dz = dims
            min_x = min(min_x, px - dx / 2.0)
            max_x = max(max_x, px + dx / 2.0)
            min_y = min(min_y, py - dy / 2.0)
            max_y = max(max_y, py + dy / 2.0)
            min_z = min(min_z, pz - dz / 2.0)
            max_z = max(max_z, pz + dz / 2.0)

        # Process each floor level
        for lvl_idx, level in enumerate(project.building.levels):
            elev = level.elevation_m

            # 1. Slabs
            for slab in level.slabs:
                s_mesh = Slab3DBuilder.build_slab_mesh(slab)
                s_mesh["floor_index"] = lvl_idx
                s_mesh["floor_name"] = level.name
                s_mesh["is_visible"] = level.is_visible
                all_meshes.append(s_mesh)
                update_bounds(s_mesh["position"], s_mesh["dimensions"])

            # 2. Walls and embedded openings
            for wall in level.walls:
                wall_pieces = Wall3DBuilder.build_wall_mesh(wall, floor_elevation_m=elev)
                for w_mesh in wall_pieces:
                    w_mesh["floor_index"] = lvl_idx
                    w_mesh["floor_name"] = level.name
                    w_mesh["is_visible"] = level.is_visible
                    all_meshes.append(w_mesh)
                    update_bounds(w_mesh["position"], w_mesh["dimensions"])

                # Door frames & window panes
                for op in wall.openings:
                    if op.element_type == "DOOR":
                        for d_mesh in Opening3DBuilder.build_door_mesh(op, wall, floor_elevation_m=elev):
                            d_mesh["floor_index"] = lvl_idx
                            d_mesh["floor_name"] = level.name
                            d_mesh["is_visible"] = level.is_visible
                            all_meshes.append(d_mesh)
                            update_bounds(d_mesh["position"], d_mesh["dimensions"])
                    elif op.element_type == "WINDOW":
                        for win_mesh in Opening3DBuilder.build_window_mesh(op, wall, floor_elevation_m=elev):
                            win_mesh["floor_index"] = lvl_idx
                            win_mesh["floor_name"] = level.name
                            win_mesh["is_visible"] = level.is_visible
                            all_meshes.append(win_mesh)
                            update_bounds(win_mesh["position"], win_mesh["dimensions"])

            # 3. Stairs
            for stair in level.stairs:
                for st_mesh in Stair3DBuilder.build_stair_mesh(stair, floor_elevation_m=elev):
                    st_mesh["floor_index"] = lvl_idx
                    st_mesh["floor_name"] = level.name
                    st_mesh["is_visible"] = level.is_visible
                    all_meshes.append(st_mesh)
                    update_bounds(st_mesh["position"], st_mesh["dimensions"])

        # Compute camera target & orbit distance
        center_x = (min_x + max_x) / 2.0 if min_x != float("inf") else 0.0
        center_y = (min_y + max_y) / 2.0 if min_y != float("inf") else 1.5
        center_z = (min_z + max_z) / 2.0 if min_z != float("inf") else 0.0

        size_x = max_x - min_x if min_x != float("inf") else 10.0
        size_y = max_y - min_y if min_y != float("inf") else 3.0
        size_z = max_z - min_z if min_z != float("inf") else 10.0
        max_extent = max(size_x, size_y, size_z, 5.0)

        camera_setup = {
            "target": [round(center_x, 3), round(center_y, 3), round(center_z, 3)],
            "initial_position": [
                round(center_x + max_extent * 1.3, 3),
                round(center_y + max_extent * 1.1, 3),
                round(center_z + max_extent * 1.3, 3)
            ],
            "near": 0.1,
            "far": round(max_extent * 20.0, 1),
            "fov": 45,
        }

        return {
            "project_id": project.project_id,
            "project_name": project.project_name,
            "units": project.units.value,
            "camera": camera_setup,
            "materials": materials_dict,
            "levels": [
                {
                    "floor_index": idx,
                    "level_id": lvl.level_id,
                    "name": lvl.name,
                    "elevation_m": lvl.elevation_m,
                    "height_m": lvl.floor_to_floor_height_m,
                    "is_visible": lvl.is_visible,
                }
                for idx, lvl in enumerate(project.building.levels)
            ],
            "meshes": all_meshes,
            "total_mesh_count": len(all_meshes),
            "bounding_box": {
                "center": [round(center_x, 3), round(center_y, 3), round(center_z, 3)],
                "dimensions": [round(size_x, 3), round(size_y, 3), round(size_z, 3)],
            }
        }

    @classmethod
    def export_to_obj(cls, project: ArchitecturalProject) -> str:
        """Export the building geometry into Wavefront OBJ format."""
        scene = cls.compile_threejs_scene(project)
        lines: List[str] = [
            f"# BuildSmart 3D Studio - OBJ Export",
            f"# Project: {project.project_name}",
            f"# Units: Meters",
            ""
        ]

        vert_offset = 1
        for m in scene["meshes"]:
            px, py, pz = m["position"]
            dx, dy, dz = m["dimensions"]
            rx, ry, rz = m.get("rotation", [0, 0, 0])

            hx, hy, hz = dx / 2.0, dy / 2.0, dz / 2.0
            # 8 corners of the box centered at origin
            corners = [
                [-hx, -hy, -hz], [hx, -hy, -hz], [hx, hy, -hz], [-hx, hy, -hz],
                [-hx, -hy, hz], [hx, -hy, hz], [hx, hy, hz], [-hx, hy, hz]
            ]

            lines.append(f"o {m['mesh_id']}")
            # Apply rotation around Y
            cos_y, sin_y = np.cos(ry), np.sin(ry)
            for cx, cy, cz in corners:
                # Rotate around Y axis
                rx_val = cx * cos_y + cz * sin_y
                rz_val = -cx * sin_y + cz * cos_y
                lines.append(f"v {px + rx_val:.4f} {py + cy:.4f} {pz + rz_val:.4f}")

            # 6 faces (quads as two triangles)
            faces = [
                (1, 2, 3), (1, 3, 4),  # Front
                (5, 8, 7), (5, 7, 6),  # Back
                (1, 5, 6), (1, 6, 2),  # Bottom
                (4, 3, 7), (4, 7, 8),  # Top
                (1, 4, 8), (1, 8, 5),  # Left
                (2, 6, 7), (2, 7, 3),  # Right
            ]
            for f in faces:
                lines.append(f"f {f[0] + vert_offset - 1} {f[1] + vert_offset - 1} {f[2] + vert_offset - 1}")

            vert_offset += 8

        return "\n".join(lines)

    @classmethod
    def export_to_glb(cls, project: ArchitecturalProject, output_path: str | Path) -> Path:
        """
        Compile project meshes into a unified trimesh scene and export as binary glTF (GLB).
        """
        scene_data = cls.compile_threejs_scene(project)
        tri_scene = trimesh.Scene()

        for m in scene_data["meshes"]:
            dx, dy, dz = m["dimensions"]
            box = trimesh.creation.box(extents=[dx, dy, dz])

            # Apply rotation
            ry = m.get("rotation", [0, 0, 0])[1]
            if abs(ry) > 0.001:
                rot_mat = trimesh.transformations.rotation_matrix(ry, [0, 1, 0])
                box.apply_transform(rot_mat)

            # Apply translation
            px, py, pz = m["position"]
            trans_mat = trimesh.transformations.translation_matrix([px, py, pz])
            box.apply_transform(trans_mat)

            # Assign color
            mat_id = m.get("material_id", "MAT-PLAS-01")
            mat_info = scene_data["materials"].get(mat_id, {})
            hex_col = mat_info.get("color", "#D3D3D3").lstrip("#")
            if len(hex_col) == 6:
                r, g, b = int(hex_col[0:2], 16), int(hex_col[2:4], 16), int(hex_col[4:6], 16)
                box.visual.face_colors = [r, g, b, 255]

            tri_scene.add_geometry(box, node_name=m["mesh_id"])

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        tri_scene.export(str(out_file), file_type="glb")
        logger.info(f"Exported 3D GLB model to {out_file}")
        return out_file
