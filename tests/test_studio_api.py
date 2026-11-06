"""
tests.test_studio_api
=====================
Direct Integration tests for BuildSmart 3D Studio route handlers.
Invokes endpoint functions directly to avoid Python 3.14 Windows socketpair issues.
"""

import pytest
from api.routes import studio
from api.routes.studio import UpdateMaterialRequest
import main


def test_studio_health():
    res = studio.studio_health_check()
    assert res["status"] == "healthy"
    assert res["subsystem"] == "BuildSmart 3D Studio"
    assert res["parsers"]["dxf"] is True
    assert res["parsers"]["trimesh"] is True


def test_studio_materials():
    mats = studio.get_studio_materials()
    assert "MAT-CONC-01" in mats
    assert "MAT-BRK-01" in mats
    assert mats["MAT-CONC-01"]["category"] == "STRUCTURAL"


def test_studio_seed_sample_and_retrieval():
    # Seed sample project
    seed_res = studio.seed_sample_studio_project()
    assert seed_res["status"] == "success"
    proj_id = seed_res["project_id"]

    # Retrieve project model
    proj = studio.get_studio_project(proj_id)
    assert proj["project_name"] == "Contemporary 2-Story Villa (Seed Model)"
    assert len(proj["building"]["levels"]) == 2

    # Retrieve BIM Tree
    tree = studio.get_studio_bim_tree(proj_id)
    assert len(tree["levels"]) == 2
    assert "building_elements" in tree


def test_studio_scene_graph():
    scene = studio.get_studio_scene("STU-SAMPLE-2BHK")
    assert scene["project_id"] == "STU-SAMPLE-2BHK"
    assert "camera" in scene
    assert "materials" in scene
    assert len(scene["meshes"]) >= 10
    assert scene["bounding_box"]["dimensions"][0] > 0


def test_studio_export_obj():
    res = studio.export_project_obj("STU-SAMPLE-2BHK")
    body = res.body.decode("utf-8") if hasattr(res, "body") else str(res)
    assert "v " in body
    assert "f " in body
    assert "BuildSmart 3D Studio" in body


def test_studio_export_glb():
    res = studio.export_project_glb("STU-SAMPLE-2BHK")
    # FileResponse returns a valid path
    import os
    assert os.path.exists(res.path)
    assert os.path.getsize(res.path) > 500


def test_studio_material_update():
    payload = UpdateMaterialRequest(material_id="MAT-BRK-01")
    res = studio.update_element_material("STU-SAMPLE-2BHK", "GF_W_FRONT", payload)
    assert res["status"] == "success"
    assert res["material_id"] == "MAT-BRK-01"


def test_serve_studio_html():
    res = main.serve_studio()
    import os
    assert os.path.exists(res.path)
    assert "studio.html" in res.path
