"""
tests.test_studio_recognition
=============================
Unit tests for Milestone 3: Architectural Recognition Engine.
Tests:
- WallDetector: parallel pairing, thickness calculation, centerline extraction.
- OpeningDetector: door swing projection, window attachment to walls.
- RoomExtractor: closed polygon room detection & semantic labeling.
- PlanAnalyzer: end-to-end DXF to ArchitecturalProject conversion.
"""

import tempfile
from pathlib import Path
import pytest
import ezdxf

from studio.models.geometry import Point2D
from studio.models.elements import WallType, RoomType, ElementType
from studio.recognition.wall_detector import WallDetector
from studio.recognition.opening_detector import OpeningDetector
from studio.recognition.room_extractor import RoomExtractor
from studio.recognition.plan_analyzer import PlanAnalyzer


def test_wall_detector_parallel_pairing():
    detector = WallDetector()

    # Two parallel lines 0.23m apart along X axis from X=0 to X=8
    lines = [
        {"layer": "WALL", "category": "WALL", "start": {"x": 0.0, "y": 0.0}, "end": {"x": 8.0, "y": 0.0}},
        {"layer": "WALL", "category": "WALL", "start": {"x": 0.0, "y": 0.23}, "end": {"x": 8.0, "y": 0.23}},
    ]

    walls = detector.from_cad_lines(lines)
    assert len(walls) == 1
    w = walls[0]
    assert w.length_m == 8.0
    assert abs(w.thickness_m - 0.23) < 0.01
    assert w.wall_type == WallType.EXTERIOR
    assert w.start.y == 0.115


def test_opening_detector_door_and_window():
    detector = WallDetector()
    opening_det = OpeningDetector()

    # Create host wall along X axis from (0,0) to (10,0)
    lines = [
        {"layer": "WALL", "category": "WALL", "start": {"x": 0.0, "y": 0.0}, "end": {"x": 10.0, "y": 0.0}},
    ]
    walls = detector.from_cad_lines(lines)
    assert len(walls) == 1
    wall = walls[0]

    # Door swing arc at (3, 0) with radius 0.9m
    arcs = [
        {"layer": "DOOR", "center": {"x": 3.0, "y": 0.1}, "radius_m": 0.9, "start_angle_deg": 0, "end_angle_deg": 90}
    ]
    doors = opening_det.detect_doors_from_arcs(arcs, walls)
    assert len(doors) == 1
    assert doors[0].width_m == 0.9
    assert doors[0].wall_id == wall.wall_id
    assert len(wall.openings) == 1

    # Window line along wall at (7, 0) to (8.5, 0)
    win_lines = [
        {"layer": "A-GLAZ", "category": "WINDOW", "start": {"x": 7.0, "y": 0.0}, "end": {"x": 8.5, "y": 0.0}}
    ]
    windows = opening_det.detect_windows_from_cad(win_lines, walls)
    assert len(windows) == 1
    assert windows[0].width_m == 1.5
    assert len(wall.openings) == 2


def test_room_extractor_labeling():
    extractor = RoomExtractor()

    polylines = [
        {
            "layer": "ROOMS",
            "is_closed": True,
            "points": [
                {"x": 0.0, "y": 0.0},
                {"x": 5.0, "y": 0.0},
                {"x": 5.0, "y": 4.0},
                {"x": 0.0, "y": 4.0},
            ]
        }
    ]
    texts = [
        {"text": "Master Bedroom", "position": {"x": 2.5, "y": 2.0}}
    ]

    rooms = extractor.from_cad_polylines_and_text(polylines, texts)
    assert len(rooms) == 1
    r = rooms[0]
    assert r.room_type == RoomType.MASTER_BEDROOM
    assert r.name == "Master Bedroom"
    assert r.area_sqm == 20.0


def test_plan_analyzer_end_to_end():
    with tempfile.TemporaryDirectory() as tmpdir:
        dxf_path = Path(tmpdir) / "sample_residence.dxf"

        # Generate sample DXF
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 6
        msp = doc.modelspace()

        # Walls forming a 10m x 8m room
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "A-WALL"})
        msp.add_line((10, 0), (10, 8), dxfattribs={"layer": "A-WALL"})
        msp.add_line((10, 8), (0, 8), dxfattribs={"layer": "A-WALL"})
        msp.add_line((0, 8), (0, 0), dxfattribs={"layer": "A-WALL"})

        # Door swing
        msp.add_arc(center=(3, 0), radius=1.0, start_angle=0, end_angle=90, dxfattribs={"layer": "A-DOOR"})
        # Text label
        msp.add_text("Grand Living Room", dxfattribs={"layer": "TEXT"}).set_placement((5, 4))

        doc.saveas(str(dxf_path))

        analyzer = PlanAnalyzer(project_name="Grand Living Villa")
        project = analyzer.analyze_dxf(dxf_path, num_floors=2, floor_height_m=3.2)

        assert project.project_name == "Grand Living Villa"
        assert len(project.building.levels) == 2
        assert project.building.levels[0].elevation_m == 0.0
        assert project.building.levels[1].elevation_m == 3.2
        assert len(project.building.levels[0].walls) >= 4

        # BIM tree verification
        bim_tree = project.to_bim_tree_json()
        assert len(bim_tree["levels"]) == 2
        assert bim_tree["levels"][0]["walls_count"] >= 4
