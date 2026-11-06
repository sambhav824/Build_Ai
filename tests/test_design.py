import os
import pytest
from engines.geometry_engine import Rect, GeometryEngine
from agents.design_agent.design_planner import DesignPlanner
from agents.design_agent.constraint_validator import ConstraintValidator
from agents.design_agent.floorplan_generator import FloorplanGenerator
from agents.design_agent.design_revision import DesignRevision
from design.model_exporter import ModelExporter
from agents.design_agent.design_agent import DesignAgent
from api.schemas.protocol import AgentRequest

def test_rect_and_geometry():
    r1 = Rect(0, 0, 10, 10, "Room 1")
    r2 = Rect(10, 0, 10, 10, "Room 2")
    r3 = Rect(5, 5, 10, 10, "Room 3")

    assert r1.area == 100.0
    assert not r1.intersects(r2)
    assert r1.intersects(r3)

    walls = GeometryEngine.generate_walls_from_rooms([r1, r2])
    assert len(walls["exterior_walls"]) == 4
    assert len(walls["interior_walls"]) == 1

def test_design_planner_and_validator():
    setbacks = {"front_ft": 5.0, "rear_ft": 3.0, "side_left_ft": 3.0, "side_right_ft": 3.0}
    rooms = DesignPlanner.generate_layout(plot_length_ft=40.0, plot_width_ft=30.0, setbacks=setbacks, bhk="2BHK")

    assert len(rooms) >= 5
    room_names = [r.label for r in rooms]
    assert any("Living" in name for name in room_names)
    assert any("Master Bedroom" in name for name in room_names)
    assert any("Kitchen" in name for name in room_names)

    val = ConstraintValidator.validate_layout(rooms=rooms, plot_length_ft=40.0, plot_width_ft=30.0, setbacks=setbacks)
    assert val["is_valid"] is True
    assert len(val["violations"]) == 0

def test_floorplan_and_3d_exporter():
    setbacks = {"front_ft": 5.0, "rear_ft": 3.0, "side_left_ft": 3.0, "side_right_ft": 3.0}
    rooms = DesignPlanner.generate_layout(plot_length_ft=40.0, plot_width_ft=30.0, setbacks=setbacks, bhk="2BHK")

    svg_path = FloorplanGenerator.render_svg(rooms, 40.0, 30.0, "BS-DSGN-TEST")
    assert os.path.exists(svg_path)
    with open(svg_path, "r", encoding="utf-8") as f:
        content = f.read()
        assert "<svg" in content
        assert "BUILDSMARTAI ARCHITECTURAL PLAN" in content

    obj_res = ModelExporter.export_3d_obj(rooms, "BS-DSGN-TEST")
    assert os.path.exists(obj_res["obj_path"])
    assert os.path.exists(obj_res["mtl_path"])
    assert "scene_json" in obj_res

def test_conversational_design_revision():
    setbacks = {"front_ft": 5.0, "rear_ft": 3.0, "side_left_ft": 3.0, "side_right_ft": 3.0}
    rooms = DesignPlanner.generate_layout(plot_length_ft=40.0, plot_width_ft=30.0, setbacks=setbacks, bhk="2BHK")

    # Conversational modification: Increase master bedroom size
    mb_orig = next(r for r in rooms if "master bedroom" in r.label.lower())
    orig_w = mb_orig.w

    revised_rooms, notes, new_version = DesignRevision.apply_conversational_edit(
        rooms=rooms,
        instruction="Please increase master bedroom size by two feet",
        current_version=1
    )

    mb_new = next(r for r in revised_rooms if "master bedroom" in r.label.lower())
    assert mb_new.w == orig_w + 2.0
    assert new_version == 2
    assert len(notes) > 0

def test_design_agent_end_to_end():
    agent = DesignAgent()
    req = AgentRequest(
        project_id="BS-DSGN-001",
        execution_id="EXEC-DSGN-01",
        agent="design_agent",
        action="generate_layout",
        input={
            "plot_length_ft": 40.0,
            "plot_width_ft": 30.0,
            "bhk_configuration": "2BHK",
            "architectural_style": "Modern Minimalist"
        }
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert resp.requires_approval is True
    assert resp.result["version"] == 1
    assert "preview_2d_svg" in resp.result
    assert "model_3d_obj" in resp.result
    assert "scene_3d_json" in resp.result
    assert "blender_script" in resp.result
    assert os.path.exists(resp.result["model_3d_obj"])
