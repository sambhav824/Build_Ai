import os
from typing import List, Dict, Any
from engines.geometry_engine import Rect, GeometryEngine
from utils.logging_config import logger

class ModelExporter:
    """
    Procedural 3D Architectural Mesh Generator.
    Extrudes 2D layout geometry into 3D polygons, cutaways, and materials.
    Outputs standard Wavefront .obj/.mtl and structured Three.js scene JSON.
    """

    WALL_HEIGHT = 10.0 # Standard residential ceiling height in feet
    WALL_THICKNESS = 0.75 # Exterior wall thickness
    DOOR_HEIGHT = 7.0
    WINDOW_SILL = 3.0
    WINDOW_LINTEL = 7.0

    @classmethod
    def export_3d_obj(
        cls,
        rooms: List[Rect],
        project_id: str,
        output_dir: str = "generated_designs"
    ) -> Dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        obj_filename = f"{project_id}_model.obj"
        mtl_filename = f"{project_id}_model.mtl"
        obj_path = os.path.join(output_dir, obj_filename)
        mtl_path = os.path.join(output_dir, mtl_filename)

        # 1. Generate Material Library (.mtl)
        mtl_content = """# BuildSmartAI Material Library
newmtl WallPlaster
Kd 0.88 0.90 0.92
Ka 0.20 0.20 0.20
Ks 0.10 0.10 0.10
Ns 10

newmtl FloorTile
Kd 0.35 0.38 0.42
Ka 0.15 0.15 0.15
Ks 0.40 0.40 0.40
Ns 45

newmtl WindowGlass
Kd 0.25 0.55 0.85
d 0.45
illum 4

newmtl WoodDoor
Kd 0.55 0.35 0.20
Ka 0.10 0.08 0.05
Ns 20
"""
        with open(mtl_path, "w", encoding="utf-8") as f:
            f.write(mtl_content)

        # 2. Build OBJ Vertices and Faces
        vertices = []
        faces = []

        def add_quad(v1, v2, v3, v4, mtl="WallPlaster"):
            base_idx = len(vertices) + 1
            vertices.extend([v1, v2, v3, v4])
            faces.append((mtl, [base_idx, base_idx + 1, base_idx + 2, base_idx + 3]))

        # Floor Slabs for each room
        for r in rooms:
            p1 = (r.x, 0.0, r.y)
            p2 = (r.right, 0.0, r.y)
            p3 = (r.right, 0.0, r.top)
            p4 = (r.x, 0.0, r.top)
            add_quad(p1, p2, p3, p4, mtl="FloorTile")

        # Extrude Room Perimeter Walls
        for r in rooms:
            h = cls.WALL_HEIGHT
            # South wall
            add_quad((r.x, 0.0, r.y), (r.right, 0.0, r.y), (r.right, h, r.y), (r.x, h, r.y))
            # North wall
            add_quad((r.right, 0.0, r.top), (r.x, 0.0, r.top), (r.x, h, r.top), (r.right, h, r.top))
            # East wall
            add_quad((r.right, 0.0, r.y), (r.right, 0.0, r.top), (r.right, h, r.top), (r.right, h, r.y))
            # West wall
            add_quad((r.x, 0.0, r.top), (r.x, 0.0, r.y), (r.x, h, r.y), (r.x, h, r.top))

        # Write OBJ File
        with open(obj_path, "w", encoding="utf-8") as f:
            f.write(f"# BuildSmartAI Procedural 3D Mesh for {project_id}\n")
            f.write(f"mtllib {mtl_filename}\n\n")

            for v in vertices:
                f.write(f"v {v[0]:.3f} {v[1]:.3f} {v[2]:.3f}\n")
            f.write("\n")

            current_mtl = None
            for mtl, face_verts in faces:
                if mtl != current_mtl:
                    current_mtl = mtl
                    f.write(f"usemtl {mtl}\n")
                f.write(f"f {' '.join(str(i) for i in face_verts)}\n")

        # 3. Build Three.js Direct JSON Scene Descriptor (Fast browser WebGL rendering)
        three_scene = {
            "project_id": project_id,
            "wall_height": cls.WALL_HEIGHT,
            "rooms": [r.to_dict() for r in rooms],
            "camera": {
                "position": [40.0, 50.0, 60.0],
                "target": [20.0, 0.0, 20.0]
            },
            "materials": {
                "floor": {"color": "#334155", "roughness": 0.3},
                "walls": {"color": "#e2e8f0", "roughness": 0.8},
                "doors": {"color": "#854d0e"},
                "windows": {"color": "#38bdf8", "opacity": 0.5, "transparent": True}
            },
            "obj_file": obj_path.replace("\\", "/"),
            "mtl_file": mtl_path.replace("\\", "/")
        }

        scene_json_path = os.path.join(output_dir, f"{project_id}_scene.json")
        import json
        with open(scene_json_path, "w", encoding="utf-8") as f:
            json.dump(three_scene, f, indent=2)

        logger.info(f"Generated 3D Model ({obj_path}) and Three.js Scene ({scene_json_path})")
        return {
            "obj_path": obj_path.replace("\\", "/"),
            "mtl_path": mtl_path.replace("\\", "/"),
            "scene_json": three_scene
        }
