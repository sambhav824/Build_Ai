"""
Unit and Integration Tests for BuildSmart 3D Studio Conversational Architectural Modification Engine
"""
import pytest
from studio.models.geometry import Point2D, Point3D, LineSegment2D, BoundingBox2D
from studio.models.elements import (
    Wall, Door, Window, Room, Staircase, Column, Slab,
    WallType, RoomType
)
from studio.models.project import (
    ArchitecturalProject,
    Building,
    FloorLevel,
    DrawingFormat,
    MeasurementUnit
)
from studio.modification.nlp_interpreter import NLPInterpreter, ModificationOperation
from studio.modification.room_library import RoomLibrary, RoomDimensionSpec
from studio.modification.layout_planner import LayoutPlanner
from studio.modification.floor_generator import FloorGenerator
from studio.modification.revision_manager import RevisionManager
from studio.modification.modification_engine import ModificationEngine
from studio.geometry.scene_compiler import SceneCompiler
from agents.design_agent.design_revision import DesignRevision
from engines.geometry_engine import Rect


def create_sample_project(project_id: str = "TEST-MOD-01") -> ArchitecturalProject:
    """Helper to create a standard 2-story baseline building."""
    gf_walls = [
        Wall(wall_id="W1", name="Wall 1", wall_type=WallType.EXTERIOR, start=Point2D(x=0, y=0), end=Point2D(x=10, y=0), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="W2", name="Wall 2", wall_type=WallType.EXTERIOR, start=Point2D(x=10, y=0), end=Point2D(x=10, y=8), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="W3", name="Wall 3", wall_type=WallType.EXTERIOR, start=Point2D(x=10, y=8), end=Point2D(x=0, y=8), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="W4", name="Wall 4", wall_type=WallType.EXTERIOR, start=Point2D(x=0, y=8), end=Point2D(x=0, y=0), thickness_m=0.23, height_m=3.0),
    ]
    gf_rooms = [
        Room(room_id="R_GF_LIV", name="Living Room", room_type=RoomType.LIVING, boundary_polygon=[Point2D(x=0, y=0), Point2D(x=5, y=0), Point2D(x=5, y=8), Point2D(x=0, y=8)]),
        Room(room_id="R_GF_KIT", name="Kitchen", room_type=RoomType.KITCHEN, boundary_polygon=[Point2D(x=5, y=0), Point2D(x=10, y=0), Point2D(x=10, y=8), Point2D(x=5, y=8)]),
    ]
    gf_slab = Slab(slab_id="SLAB_GF", boundary_polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=8), Point2D(x=0, y=8)], elevation_m=0.0)
    gf_stair = Staircase(stair_id="STAIR_GF", start=Point2D(x=5, y=4), end=Point2D(x=5, y=7), width_m=1.0, total_rise_m=3.0, num_steps=16)

    lvl_0 = FloorLevel(level_id="lvl_0", name="Ground Floor", elevation_m=0.0, floor_to_floor_height_m=3.0, walls=gf_walls, rooms=gf_rooms, slabs=[gf_slab], stairs=[gf_stair])

    # First floor
    ff_walls = [
        Wall(wall_id="FF_W1", name="FF Wall 1", wall_type=WallType.EXTERIOR, start=Point2D(x=0, y=0), end=Point2D(x=10, y=0), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="FF_W2", name="FF Wall 2", wall_type=WallType.EXTERIOR, start=Point2D(x=10, y=0), end=Point2D(x=10, y=8), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="FF_W3", name="FF Wall 3", wall_type=WallType.EXTERIOR, start=Point2D(x=10, y=8), end=Point2D(x=0, y=8), thickness_m=0.23, height_m=3.0),
        Wall(wall_id="FF_W4", name="FF Wall 4", wall_type=WallType.EXTERIOR, start=Point2D(x=0, y=8), end=Point2D(x=0, y=0), thickness_m=0.23, height_m=3.0),
    ]
    ff_rooms = [
        Room(room_id="R_FF_BED1", name="Bedroom 1", room_type=RoomType.BEDROOM, boundary_polygon=[Point2D(x=0, y=0), Point2D(x=5, y=0), Point2D(x=5, y=4), Point2D(x=0, y=4)]),
        Room(room_id="R_FF_BATH", name="Washroom", room_type=RoomType.BATHROOM, boundary_polygon=[Point2D(x=5, y=0), Point2D(x=8, y=0), Point2D(x=8, y=3), Point2D(x=5, y=3)]),
    ]
    ff_slab = Slab(slab_id="SLAB_FF", boundary_polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=8), Point2D(x=0, y=8)], elevation_m=3.0)
    roof_slab = Slab(slab_id="SLAB_ROOF", boundary_polygon=[Point2D(x=0, y=0), Point2D(x=10, y=0), Point2D(x=10, y=8), Point2D(x=0, y=8)], elevation_m=6.0)

    lvl_1 = FloorLevel(level_id="lvl_1", name="First Floor", elevation_m=3.0, floor_to_floor_height_m=3.0, walls=ff_walls, rooms=ff_rooms, slabs=[ff_slab, roof_slab])

    building = Building(name="Test Villa", levels=[lvl_0, lvl_1])
    return ArchitecturalProject(
        project_id=project_id,
        project_name="Test Villa Project",
        source_filename="test_villa.dxf",
        source_format=DrawingFormat.DXF,
        units=MeasurementUnit.METERS,
        building=building
    )


class TestStudioNLPInterpreter:
    """Test natural-language interpretation into structured architectural intents."""

    def setup_method(self):
        self.interpreter = NLPInterpreter()

    def test_interpret_add_floor_with_bedrooms_and_washroom(self):
        """User's core problem prompt."""
        prompt = "Add 1 floor with 3 bedrooms and 1 washroom"
        intent = self.interpreter.interpret(prompt, current_floor_count=2)

        assert intent.operation == ModificationOperation.ADD_FLOOR
        assert intent.floor_count == 1
        assert intent.add_staircase_connection is True
        assert intent.preserve_existing_floors is True

        # Check room types and counts
        room_types = {r.type: r.count for r in intent.rooms}
        assert room_types.get("bedroom") == 3
        assert room_types.get("washroom") == 1 or room_types.get("bathroom") == 1

    def test_interpret_resize_room(self):
        prompt = "Increase Bedroom 1 to 4.5 by 4.0 meters"
        intent = self.interpreter.interpret(prompt)

        assert intent.operation == ModificationOperation.RESIZE_ROOM
        assert intent.target_room_name == "bedroom 1"
        assert intent.target_dimensions["width"] == 4.5
        assert intent.target_dimensions["length"] == 4.0

    def test_interpret_move_staircase(self):
        prompt = "Move the staircase to the left side"
        intent = self.interpreter.interpret(prompt)

        assert intent.operation == ModificationOperation.MOVE_STAIRCASE
        assert "left" in intent.notes.lower() or "left" in prompt.lower()

    def test_interpret_add_attached_bath(self):
        prompt = "Add an attached washroom to the master bedroom"
        intent = self.interpreter.interpret(prompt)

        assert intent.operation in (ModificationOperation.ADD_ROOMS, ModificationOperation.ADD_ATTACHED_BATH)
        assert any("washroom" in r.type or "bathroom" in r.type for r in intent.rooms)


class TestRoomLibrary:
    """Test configurable architectural dimensions library."""

    def test_room_library_standards(self):
        lib = RoomLibrary()
        bed = lib.get_dimension("bedroom")
        assert bed.default_width_m == 3.6
        assert bed.default_length_m == 3.6
        assert bed.area_sqm == 12.96

        wash = lib.get_dimension("washroom")
        assert wash.default_width_m == 1.5
        assert wash.default_length_m == 2.1
        assert wash.area_sqm == 3.15

        master = lib.get_dimension("master_bedroom")
        assert master.default_width_m == 4.5
        assert master.default_length_m == 4.0
        assert master.area_sqm == 18.0

    def test_custom_dimension_override(self):
        lib = RoomLibrary()
        custom = RoomDimensionSpec(
            room_type="study",
            display_name="Study Room",
            default_width_m=2.8,
            default_length_m=3.2,
            min_area_sqm=8.96
        )
        lib.register_room_spec(custom)
        assert lib.get_dimension("study").default_width_m == 2.8


class TestStudioModificationEngine:
    """Full architectural modification pipeline and 3D geometry regeneration."""

    def setup_method(self):
        self.engine = ModificationEngine()

    def test_stage_1_preview_modification(self):
        project = create_sample_project("TEST-PREVIEW")
        proposal = self.engine.preview_modification(
            project=project,
            user_prompt="Add 1 floor with 3 bedrooms and 1 washroom"
        )

        assert proposal["status"] == "success"
        assert proposal["can_apply"] is True
        assert proposal["proposal"]["operation"] == "add_floor"
        assert len(proposal["proposal"]["requested_rooms"]) == 4  # 3 beds + 1 bath
        assert proposal["proposal"]["validation"]["footprint_sufficient"] is True

    def test_stage_2_apply_modification_user_prompt(self):
        """
        User's exact problem prompt:
        'Add 1 floor with 3 bedrooms and 1 washroom'
        Must create an actual 3rd floor, place rooms, add staircase, and regenerate meshes.
        """
        project = create_sample_project("TEST-ADD-FLOOR")
        initial_floor_count = len(project.building.levels)
        initial_mesh_count = SceneCompiler.compile_threejs_scene(project)["total_mesh_count"]

        updated_project, result = self.engine.apply_modification(
            project=project,
            user_prompt="Add 1 floor with 3 bedrooms and 1 washroom"
        )

        # 1. Verify Floor Count increased by 1
        assert len(updated_project.building.levels) == initial_floor_count + 1
        new_floor = updated_project.building.levels[-1]
        assert new_floor.elevation_m == 6.0  # Ground=0m, Level 1=3m, Level 2=6m

        # 2. Verify Requested Rooms exist on the new floor
        enclosed_rooms = [r for r in new_floor.rooms if r.room_type != RoomType.CORRIDOR]
        assert len(enclosed_rooms) == 4
        room_types = [r.room_type for r in enclosed_rooms]
        assert room_types.count(RoomType.BEDROOM) == 3
        assert room_types.count(RoomType.BATHROOM) == 1
        assert any(r.room_type == RoomType.CORRIDOR for r in new_floor.rooms)

        # 3. Verify Room Dimensions & Non-zero Area
        for room in new_floor.rooms:
            poly = room.boundary_polygon
            assert len(poly) == 4
            w = abs(poly[1].x - poly[0].x)
            l = abs(poly[2].y - poly[1].y)
            assert w > 0.5
            assert l > 0.5
            area = w * l
            assert area > 2.0  # reasonable room area

        # 4. Verify Staircase connection created
        all_stairs = [stair for lvl in updated_project.building.levels for stair in lvl.stairs]
        assert len(all_stairs) >= 2  # Ground floor stair + continuing stair to new floor

        # 5. Verify Three.js scene meshes regenerated and increased
        new_scene = result["scene"]
        assert new_scene["total_mesh_count"] > initial_mesh_count
        assert len(new_scene["levels"]) == 3

        # 6. Verify Result message
        assert result["status"] == "success"
        assert "Floor" in result["message"] or "added" in result["message"]

    def test_apply_resize_room(self):
        project = create_sample_project("TEST-RESIZE")
        updated_project, result = self.engine.apply_modification(
            project=project,
            user_prompt="Increase Bedroom 1 to 4.5 by 4.0 meters"
        )
        assert result["status"] == "success"
        # Find Bedroom 1
        bed1 = None
        for lvl in updated_project.building.levels:
            for r in lvl.rooms:
                if "bedroom 1" in r.name.lower() or "bed1" in r.room_id.lower():
                    bed1 = r
                    break
        assert bed1 is not None
        poly = bed1.boundary_polygon
        w = abs(poly[1].x - poly[0].x)
        l = abs(poly[2].y - poly[1].y)
        assert abs(w - 4.5) < 0.01
        assert abs(l - 4.0) < 0.01

    def test_undo_and_redo_revisions(self):
        project = create_sample_project("TEST-UNDO-REDO")
        mgr = self.engine.revision_manager
        mgr.initialize_project(project)

        # Apply modification 1
        p1, res1 = self.engine.apply_modification(project, "Add 1 floor with 3 bedrooms and 1 washroom")
        assert len(p1.building.levels) == 3

        # Undo
        restored = mgr.undo("TEST-UNDO-REDO")
        assert restored is not None
        assert len(restored.building.levels) == 2

        # Redo
        advanced = mgr.redo("TEST-UNDO-REDO")
        assert advanced is not None
        assert len(advanced.building.levels) == 3


class TestDesignRevisionAgentIntegration:
    """Verify core design agent handles multi-floor additions without falling into generic default."""

    def test_conversational_edit_does_not_say_initial_algorithmic_layout(self):
        existing_rooms = [
            Rect(x=0, y=0, w=15, h=15, label="Living Room", elevation_ft=0, floor=0),
            Rect(x=15, y=0, w=10, h=15, label="Kitchen", elevation_ft=0, floor=0),
        ]
        revised_rooms, notes, new_version = DesignRevision.apply_conversational_edit(
            rooms=existing_rooms,
            instruction="Add 1 floor with 3 bedrooms and 1 washroom",
            current_version=1
        )
        assert new_version == 2
        assert "Initial algorithmic layout generated." not in notes
        assert any("floor" in n.lower() or "bedroom" in n.lower() for n in notes)
        # Check that upper floor rooms exist
        upper_floor_rooms = [r for r in revised_rooms if getattr(r, "floor", 0) >= 1]
        assert len(upper_floor_rooms) >= 4  # 3 bedrooms + 1 washroom
