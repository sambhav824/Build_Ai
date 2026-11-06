"""
tests.test_studio_models
========================
Unit tests for BuildSmart 3D Studio Intermediate Representation Models:
- Point2D, Point3D, LineSegment2D, BoundingBox2D
- Wall, Door, Window, Room, Staircase, Column, Slab
- FloorLevel, Building, ArchitecturalProject
- BIM Tree hierarchy generation and JSON serialization
"""

import pytest
from studio.models.geometry import Point2D, Point3D, LineSegment2D, BoundingBox2D, polygon_area, polygon_perimeter
from studio.models.materials import STANDARD_MATERIALS, MaterialCategory
from studio.models.elements import (
    Wall, Door, Window, Room, Staircase, Column, Slab,
    ElementType, WallType, DoorType, WindowType, RoomType, ConfidenceLevel
)
from studio.models.project import ArchitecturalProject, Building, FloorLevel, DrawingFormat, MeasurementUnit


def test_geometry_primitives():
    p1 = Point2D(x=0.0, y=0.0)
    p2 = Point2D(x=4.0, y=3.0)
    assert p1.distance_to(p2) == 5.0
    
    seg = LineSegment2D(start=p1, end=p2)
    assert seg.length == 5.0
    assert seg.midpoint.x == 2.0
    assert seg.midpoint.y == 1.5

    pts = [Point2D(x=0, y=0), Point2D(x=4, y=0), Point2D(x=4, y=3), Point2D(x=0, y=3)]
    assert polygon_area(pts) == 12.0
    assert polygon_perimeter(pts) == 14.0


def test_wall_and_openings():
    door = Door(
        opening_id="D01",
        element_type=ElementType.DOOR,
        door_type=DoorType.SINGLE_SWING,
        width_m=1.0,
        height_m=2.1,
        wall_id="W01",
        sill_height_m=0.0,
        confidence=0.95,
        confidence_level=ConfidenceLevel.HIGH
    )
    window = Window(
        opening_id="WN01",
        element_type=ElementType.WINDOW,
        window_type=WindowType.SLIDING,
        width_m=1.5,
        height_m=1.2,
        sill_height_m=0.9,
        wall_id="W01",
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH
    )

    wall = Wall(
        wall_id="W01",
        element_type=ElementType.WALL,
        wall_type=WallType.EXTERIOR,
        start=Point2D(x=0.0, y=0.0),
        end=Point2D(x=8.0, y=0.0),
        thickness_m=0.23,
        height_m=3.0,
        openings=[door, window],
        material_id="MAT-BRK-01"
    )

    assert wall.length_m == 8.0
    assert len(wall.openings) == 2
    assert wall.wall_type == WallType.EXTERIOR
    assert wall.gross_area_sqm == 24.0
    assert wall.net_area_sqm == 24.0 - (1.0 * 2.1 + 1.5 * 1.2)


def test_room_and_elements():
    room = Room(
        room_id="R01",
        name="Living Room",
        room_type=RoomType.LIVING,
        boundary_polygon=[
            Point2D(x=0, y=0),
            Point2D(x=5, y=0),
            Point2D(x=5, y=4),
            Point2D(x=0, y=4)
        ]
    )
    assert room.area_sqm == 20.0
    assert room.room_type == RoomType.LIVING
    assert room.width_m == 5.0
    assert room.length_m == 4.0


def test_architectural_project_and_bim_tree():
    # Construct complete 2-floor project
    f0 = FloorLevel(
        name="Ground Floor",
        elevation_m=0.0,
        walls=[
            Wall(
                wall_id="GF_W01",
                start=Point2D(x=0, y=0),
                end=Point2D(x=6, y=0),
                thickness_m=0.23,
                height_m=3.0,
                openings=[
                    Door(opening_id="GF_D1", width_m=1.0, height_m=2.1),
                    Window(opening_id="GF_WND1", width_m=1.2, height_m=1.2)
                ]
            ),
            Wall(
                wall_id="GF_W02",
                start=Point2D(x=6, y=0),
                end=Point2D(x=6, y=5),
                thickness_m=0.23,
                height_m=3.0
            )
        ],
        rooms=[
            Room(
                room_id="GF_R1",
                name="Living Room",
                room_type=RoomType.LIVING,
                boundary_polygon=[Point2D(x=0,y=0), Point2D(x=6,y=0), Point2D(x=6,y=5), Point2D(x=0,y=5)]
            )
        ],
        slabs=[
            Slab(
                slab_id="GF_SLAB1",
                boundary_polygon=[Point2D(x=0,y=0), Point2D(x=6,y=0), Point2D(x=6,y=5), Point2D(x=0,y=5)],
                thickness_m=0.15
            )
        ]
    )

    f1 = FloorLevel(
        name="First Floor",
        elevation_m=3.0,
        walls=[
            Wall(
                wall_id="FF_W01",
                start=Point2D(x=0, y=0),
                end=Point2D(x=6, y=0),
                thickness_m=0.15,
                height_m=3.0
            )
        ],
        rooms=[
            Room(
                room_id="FF_R1",
                name="Master Bedroom",
                room_type=RoomType.BEDROOM,
                boundary_polygon=[Point2D(x=0,y=0), Point2D(x=6,y=0), Point2D(x=6,y=5), Point2D(x=0,y=5)]
            )
        ],
        slabs=[
            Slab(
                slab_id="FF_SLAB1",
                boundary_polygon=[Point2D(x=0,y=0), Point2D(x=6,y=0), Point2D(x=6,y=5), Point2D(x=0,y=5)],
                thickness_m=0.15,
                elevation_m=3.0
            )
        ]
    )

    bldg = Building(
        building_id="BLDG_01",
        name="Villa Prime",
        levels=[f0, f1]
    )

    project = ArchitecturalProject(
        project_id="PROJ_TEST_101",
        project_name="Prime Villa Residence",
        source_filename="villa_plan.dxf",
        source_format=DrawingFormat.DXF,
        units=MeasurementUnit.METERS,
        building=bldg
    )

    # Test serialization
    dump = project.model_dump()
    assert dump["project_id"] == "PROJ_TEST_101"
    assert len(dump["building"]["levels"]) == 2

    # Test BIM Tree generation (for left panel in Studio UI)
    bim_tree = project.to_bim_tree_json()
    assert bim_tree["project_id"] == "PROJ_TEST_101"
    assert len(bim_tree["levels"]) == 2
    assert "building_elements" in bim_tree
    
    # Check elements count
    elem_categories = [item["category"] for item in bim_tree["building_elements"]]
    assert "Wall" in elem_categories
    assert "Door" in elem_categories
    assert "Window" in elem_categories
    assert "Room" in elem_categories
    assert "Slab" in elem_categories

    wall_entry = next(item for item in bim_tree["building_elements"] if item["category"] == "Wall")
    assert wall_entry["count"] == 3
