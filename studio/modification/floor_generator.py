"""
studio.modification.floor_generator
===================================
Multi-Floor Generation & Vertical Staircase Continuation Engine.
Manages adding new stories, preserving lower floors, generating vertical circulation
stairwells, and placing room layouts within structural footprint constraints.
"""

from typing import List, Dict, Any, Optional, Tuple
from studio.models.geometry import Point2D, BoundingBox2D
from studio.models.elements import (
    Wall, Door, Window, Room, Slab, Staircase,
    ElementType, WallType, StairType
)
from studio.models.project import FloorLevel, Building, ArchitecturalProject
from studio.modification.layout_planner import LayoutPlanner
from studio.modification.room_library import RoomLibrary
from utils.logging_config import logger


class FloorGenerator:
    """
    Intelligent floor addition and vertical building assembly engine.
    """

    def __init__(self, room_library: Optional[RoomLibrary] = None):
        self.library = room_library or RoomLibrary()
        self.planner = LayoutPlanner(self.library)

    def extract_building_footprint(self, building: Building) -> BoundingBox2D:
        """Extract the boundary footprint from existing building walls and slabs."""
        all_pts: List[Point2D] = []
        for lvl in building.levels:
            for s in lvl.slabs:
                all_pts.extend(s.boundary_polygon)
            for w in lvl.walls:
                all_pts.extend([w.start, w.end])
            for r in lvl.rooms:
                all_pts.extend(r.boundary_polygon)

        if not all_pts:
            # Fallback standard 12m x 9m residential footprint
            return BoundingBox2D(min_x=0.0, min_y=0.0, max_x=12.0, max_y=9.0)

        return BoundingBox2D.from_points(all_pts)

    def add_floors(
        self,
        project: ArchitecturalProject,
        additional_floor_count: int = 1,
        floor_name_override: Optional[str] = None,
        rooms_requested: Optional[List[Dict[str, Any]]] = None,
        floor_height_m: float = 3.0,
        add_staircase: bool = True
    ) -> Tuple[ArchitecturalProject, Dict[str, Any]]:
        """
        Add one or more floors to an existing architectural project.
        Preserves lower stories intact, calculates new elevations, places rooms,
        and generates matching multi-story staircase flights.
        """
        building = project.building
        existing_floor_count = len(building.levels)
        footprint = self.extract_building_footprint(building)

        logger.info(
            f"Adding {additional_floor_count} floor(s) to project {project.project_id}. "
            f"Current floors: {existing_floor_count}. Footprint: {footprint.width}m x {footprint.height}m"
        )

        # Inspect existing staircase location in lower floors
        existing_stair: Optional[Staircase] = None
        for lvl in building.levels:
            if lvl.stairs:
                existing_stair = lvl.stairs[0]
                break

        # If no staircase exists in the building and multi-floor is requested, add one on ground floor
        if add_staircase and not existing_stair and building.levels:
            # Place standard straight staircase flight near corridor
            stair_start = Point2D(x=footprint.min_x + footprint.width * 0.65, y=footprint.min_y + footprint.height * 0.55)
            stair_end = Point2D(x=stair_start.x, y=stair_start.y + 2.8)
            gf_stair = Staircase(
                stair_id=f"STAIR_L0_01",
                start=stair_start,
                end=stair_end,
                width_m=1.0,
                total_rise_m=floor_height_m,
                num_steps=16,
                material_id="MAT-WOOD-01"
            )
            building.levels[0].stairs.append(gf_stair)
            existing_stair = gf_stair
            logger.info("Created missing Ground Floor staircase connection.")

        added_levels: List[FloorLevel] = []
        stair_zone = None
        if existing_stair:
            stair_zone = BoundingBox2D.from_points([existing_stair.start, existing_stair.end])

        default_room_reqs = rooms_requested if rooms_requested else [
            {"type": "master_bedroom", "count": 1},
            {"type": "bedroom", "count": 2},
            {"type": "washroom", "count": 1}
        ]

        for i in range(additional_floor_count):
            floor_idx = existing_floor_count + i
            elev = floor_idx * floor_height_m

            lvl_name = floor_name_override if (floor_name_override and additional_floor_count == 1) else (
                "First Floor" if floor_idx == 1 else (
                    "Second Floor" if floor_idx == 2 else f"Level {floor_idx + 1}"
                )
            )

            # Synthesize floor plan layout (walls, rooms, doors, windows, slab)
            layout = self.planner.plan_floor_layout(
                footprint=footprint,
                rooms_requested=default_room_reqs,
                staircase_zone=stair_zone,
                floor_elevation_m=elev,
                floor_height_m=floor_height_m
            )

            # Build continuing staircase flight for this floor
            level_stairs: List[Staircase] = []
            if add_staircase and existing_stair:
                stair_continuation = Staircase(
                    stair_id=f"STAIR_L{floor_idx}_01",
                    start=existing_stair.start,
                    end=existing_stair.end,
                    width_m=existing_stair.width_m,
                    total_rise_m=floor_height_m,
                    num_steps=16,
                    material_id=existing_stair.material_id
                )
                level_stairs.append(stair_continuation)

            # Slabs: Floor slab + Roof capping slab
            slabs = [layout["slab"]]
            # Add roof capping slab above the highest floor
            if i == additional_floor_count - 1:
                roof_slab = Slab(
                    slab_id=f"ROOF_SLAB_TOP",
                    name="Roof Terrace Slab",
                    boundary_polygon=layout["slab"].boundary_polygon,
                    thickness_m=0.15,
                    elevation_m=elev + floor_height_m,
                    material_id="MAT-CONC-01"
                )
                slabs.append(roof_slab)

            new_level = FloorLevel(
                level_id=f"lvl_{floor_idx + 1}",
                name=lvl_name,
                elevation_m=elev,
                floor_to_floor_height_m=floor_height_m,
                default_wall_height_m=floor_height_m,
                walls=layout["walls"],
                rooms=layout["rooms"],
                slabs=slabs,
                stairs=level_stairs
            )

            building.levels.append(new_level)
            added_levels.append(new_level)

        summary = {
            "operation": "add_floor",
            "notes": f"Added {additional_floor_count} Floor(s) with rooms, corridor, and connecting staircase.",
            "floors_added": additional_floor_count,
            "new_total_floors": len(building.levels),
            "new_total_height_m": building.total_height_m,
            "new_builtup_sqm": building.total_builtup_area_sqm,
            "added_levels": [{"name": l.name, "elevation_m": l.elevation_m, "rooms_count": len(l.rooms)} for l in added_levels]
        }

        logger.info(f"Successfully generated {additional_floor_count} floor(s). Total height: {building.total_height_m}m")
        return project, summary
