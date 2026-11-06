"""
tests.test_studio_geometry
==========================
Unit tests for Milestone 4: 3D Geometry Generation Engine.
Tests:
- Wall3DBuilder: procedural wall segmentation with openings.
- Slab3DBuilder: floor slab mesh generation.
- Opening3DBuilder: door frames and glass panes.
- SceneCompiler: Three.js scene graph JSON synthesis, OBJ text generation, and GLB binary export.
"""

import tempfile
from pathlib import Path
import pytest

from studio.models.geometry import Point2D
from studio.models.elements import Wall, Door, Window, Slab, ElementType, WallType, DoorType, WindowType
from studio.models.project import ArchitecturalProject, Building, FloorLevel, DrawingFormat
from studio.geometry.wall_builder import Wall3DBuilder
from studio.geometry.slab_builder import Slab3DBuilder
from studio.geometry.opening_builder import Opening3DBuilder
from studio.geometry.scene_compiler import SceneCompiler


def test_wall_3d_builder_segmentation():
    # 8-meter wall with door at offset 2m and window at offset 6m
    door = Door(opening_id="D1", width_m=1.0, height_m=2.1, offset_along_wall_m=2.0)
    win = Window(opening_id="W1", width_m=1.5, height_m=1.2, sill_height_m=0.9, offset_along_wall_m=6.0)

    wall = Wall(
        wall_id="W_TEST_01",
        start=Point2D(x=0.0, y=0.0),
        end=Point2D(x=8.0, y=0.0),
        thickness_m=0.23,
        height_m=3.0,
        openings=[door, win]
    )

    meshes = Wall3DBuilder.build_wall_mesh(wall, floor_elevation_m=0.0)
    # Should include piers, lintel above door, lintel above window, sill below window
    assert len(meshes) >= 4
    categories = [m["category"] for m in meshes]
    assert all(c == "Wall" for c in categories)


def test_slab_3d_builder():
    slab = Slab(
        slab_id="SLAB_GF",
        boundary_polygon=[
            Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=8), Point2D(x=0, y=8)
        ],
        thickness_m=0.15,
        elevation_m=0.0
    )
    mesh = Slab3DBuilder.build_slab_mesh(slab)
    assert mesh["category"] == "Slab"
    assert mesh["dimensions"] == [10.0, 0.15, 8.0]


def test_scene_compiler_and_exports():
    # Setup test project
    f0 = FloorLevel(
        name="Ground Floor",
        elevation_m=0.0,
        walls=[
            Wall(
                wall_id="W01",
                start=Point2D(x=0, y=0),
                end=Point2D(x=6, y=0),
                thickness_m=0.23,
                height_m=3.0,
                openings=[Door(opening_id="D01", width_m=1.0, height_m=2.1, offset_along_wall_m=3.0)]
            )
        ],
        slabs=[
            Slab(
                slab_id="SLAB01",
                boundary_polygon=[Point2D(x=0, y=0), Point2D(x=6, y=0), Point2D(x=6, y=4), Point2D(x=0, y=4)],
                thickness_m=0.15
            )
        ]
    )

    proj = ArchitecturalProject(
        project_name="Test Export Project",
        building=Building(levels=[f0])
    )

    # 1. Three.js Scene Graph
    scene = SceneCompiler.compile_threejs_scene(proj)
    assert scene["project_name"] == "Test Export Project"
    assert "materials" in scene
    assert "camera" in scene
    assert len(scene["meshes"]) >= 3  # wall piers, lintel, door frame, slab

    # 2. OBJ Export
    obj_str = SceneCompiler.export_to_obj(proj)
    assert "v " in obj_str
    assert "f " in obj_str
    assert "BuildSmart 3D Studio" in obj_str

    # 3. GLB Export
    with tempfile.TemporaryDirectory() as tmpdir:
        glb_path = Path(tmpdir) / "model.glb"
        SceneCompiler.export_to_glb(proj, glb_path)
        assert glb_path.exists()
        assert glb_path.stat().st_size > 500  # Non-empty valid binary glTF
