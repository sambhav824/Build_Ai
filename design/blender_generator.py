import os
import json
from typing import List, Dict, Any
from engines.geometry_engine import Rect
from utils.logging_config import logger

class BlenderGenerator:
    """
    Generates standalone procedural Python scripts for Blender (`bpy`)
    allowing builders and architects to render high-fidelity photorealistic
    images and dollhouse cutaways via `blender --background --python render.py`.
    """

    @staticmethod
    def generate_blender_script(
        rooms: List[Rect],
        project_id: str,
        output_script_path: str = None
    ) -> str:
        if not output_script_path:
            os.makedirs("generated_designs", exist_ok=True)
            output_script_path = f"generated_designs/{project_id}_blender_build.py"

        rooms_data = [r.to_dict() for r in rooms]
        rooms_json_str = json.dumps(rooms_data, indent=2)

        script_content = f"""# BuildSmartAI Procedural Blender Script for {project_id}
# Run with: blender --background --python {os.path.basename(output_script_path)}
import bpy
import bmesh
import json

# Clear default startup scene
bpy.ops.wm.read_factory_settings(use_empty=True)

# Rooms payload
rooms = {rooms_json_str}
wall_height = 3.0 # meters (~10 ft)

# Setup Collection
collection = bpy.data.collections.new("BuildSmartAI_House")
bpy.context.scene.collection.children.link(collection)

# Setup Materials
def make_mat(name, color_rgba, roughness=0.5):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = color_rgba
        bsdf.inputs["Roughness"].default_value = roughness
    return mat

wall_mat = make_mat("PlasterWall", (0.9, 0.92, 0.94, 1.0), roughness=0.8)
floor_mat = make_mat("FloorTile", (0.3, 0.33, 0.38, 1.0), roughness=0.3)

for r in rooms:
    # Scale from feet to meters (0.3048)
    x = r["x"] * 0.3048
    y = r["y"] * 0.3048
    w = r["w"] * 0.3048
    h = r["h"] * 0.3048

    # 1. Floor Mesh
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=(x + (w/2.0), y + (h/2.0), 0.0))
    floor_obj = bpy.context.active_object
    floor_obj.name = f"Floor_{{r['name']}}"
    floor_obj.scale = (w, h, 1.0)
    floor_obj.data.materials.append(floor_mat)

    # 2. Extrude Perimeter Walls
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x + (w/2.0), y + (h/2.0), wall_height/2.0))
    wall_obj = bpy.context.active_object
    wall_obj.name = f"Walls_{{r['name']}}"
    wall_obj.scale = (w, h, wall_height)
    wall_obj.data.materials.append(wall_mat)

# Setup Sun Lamp & Dollhouse Camera
bpy.ops.object.light_add(type='SUN', location=(15, 10, 20))
sun = bpy.context.active_object
sun.data.energy = 4.0

bpy.ops.object.camera_add(location=(12, -18, 16), rotation=(1.05, 0.0, 0.58))
bpy.context.scene.camera = bpy.context.active_object

print("BuildSmartAI: Blender model generation completed.")
"""
        with open(output_script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        logger.info(f"Generated Blender Python automation script: {output_script_path}")
        return output_script_path
