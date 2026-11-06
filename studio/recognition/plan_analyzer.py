"""
studio.recognition.plan_analyzer
================================
Master Architectural Drawing Recognition Engine.
Orchestrates parsers, wall detectors, opening detectors, and room extractors
to produce a complete SI-calibrated ArchitecturalProject intermediate representation.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import cv2
import numpy as np
from studio.models.project import (
    ArchitecturalProject,
    Building,
    FloorLevel,
    DrawingFormat,
    MeasurementUnit,
)
from studio.models.elements import Wall, Door, Window, Room, Slab, Column, ConfidenceLevel, WallType
from studio.models.geometry import Point2D, BoundingBox2D
from studio.parsers.dxf_parser import DXFParser
from studio.parsers.pdf_processor import PDFProcessor
from studio.parsers.raster_preprocessor import RasterPreprocessor
from studio.parsers.scale_calibrator import ScaleCalibrator
from studio.recognition.wall_detector import WallDetector
from studio.recognition.opening_detector import OpeningDetector
from studio.recognition.room_extractor import RoomExtractor
from utils.logging_config import logger

STUDIO_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "studio_projects"
STUDIO_DATA_DIR.mkdir(parents=True, exist_ok=True)


class PlanAnalyzer:
    """
    Central Architectural Plan Analyzer.
    Deterministically transforms 2D CAD or raster drawings into complete 3D-ready project records.
    """

    def __init__(self, project_name: str = "Architectural Building Model"):
        self.project_name = project_name
        self.wall_detector = WallDetector()
        self.opening_detector = OpeningDetector()
        self.room_extractor = RoomExtractor()

    def analyze_dxf(self, dxf_path: str | Path, num_floors: int = 1, floor_height_m: float = 3.0) -> ArchitecturalProject:
        """Analyze a CAD DXF file into a complete multi-floor ArchitecturalProject."""
        path = Path(dxf_path)
        logger.info(f"Analyzing DXF architectural drawing: {path.name}")

        parser = DXFParser(path)
        cad_data = parser.extract_entities()

        # 1. Detect walls
        walls = self.wall_detector.from_cad_lines(cad_data["lines"])

        # 2. Detect door swings and attach to walls
        doors = self.opening_detector.detect_doors_from_arcs(cad_data["arcs"], walls)

        # 3. Detect windows and attach to walls
        windows = self.opening_detector.detect_windows_from_cad(cad_data["lines"], walls)

        # 4. Extract rooms from closed polylines and text annotations
        rooms = self.room_extractor.from_cad_polylines_and_text(cad_data["polylines"], cad_data["texts"])

        # 5. Compute overall building bounding footprint
        all_pts: List[Point2D] = []
        for w in walls:
            all_pts.extend([w.start, w.end])
        for r in rooms:
            all_pts.extend(r.boundary_polygon)

        bbox = BoundingBox2D.from_points(all_pts)
        footprint_polygon = [
            Point2D(x=bbox.min_x, y=bbox.min_y),
            Point2D(x=bbox.max_x, y=bbox.min_y),
            Point2D(x=bbox.max_x, y=bbox.max_y),
            Point2D(x=bbox.min_x, y=bbox.max_y),
        ]

        # 6. Construct multi-floor building levels
        levels: List[FloorLevel] = []
        for f_idx in range(max(1, num_floors)):
            elevation = round(f_idx * floor_height_m, 2)
            level_name = "Ground Floor" if f_idx == 0 else f"Level {f_idx + 1}"

            # Create floor slab
            slab = Slab(
                slab_id=f"SLAB_L{f_idx + 1}_01",
                boundary_polygon=footprint_polygon,
                thickness_m=0.15,
                elevation_m=elevation
            )

            # Replicate walls for upper floors if multi-story
            level_walls: List[Wall] = []
            for w in walls:
                # Shallow copy wall with floor-specific ID
                copied_openings = [op.model_copy() for op in w.openings]
                copied_wall = Wall(
                    wall_id=f"L{f_idx + 1}_{w.wall_id}",
                    start=w.start,
                    end=w.end,
                    thickness_m=w.thickness_m,
                    height_m=w.height_m,
                    wall_type=w.wall_type,
                    openings=copied_openings,
                    confidence=w.confidence,
                    confidence_level=w.confidence_level
                )
                level_walls.append(copied_wall)

            level = FloorLevel(
                level_id=f"lvl_{f_idx + 1}",
                name=level_name,
                elevation_m=elevation,
                floor_to_floor_height_m=floor_height_m,
                default_wall_height_m=floor_height_m,
                walls=level_walls,
                rooms=[r.model_copy() for r in rooms],
                slabs=[slab]
            )
            levels.append(level)

        building = Building(
            name=self.project_name,
            levels=levels
        )

        project = ArchitecturalProject(
            project_name=self.project_name,
            source_filename=path.name,
            source_format=DrawingFormat.DXF,
            units=MeasurementUnit.METERS,
            scale_verified=True,
            building=building,
            metadata={
                "cad_layers": cad_data["layers"],
                "total_cad_entities": cad_data["total_entity_count"],
                "bounding_box": cad_data["bounding_box"],
            }
        )

        # Persist project JSON
        out_file = STUDIO_DATA_DIR / f"{project.project_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))

        logger.info(f"Successfully analyzed DXF into ArchitecturalProject {project.project_id}")
        return project

    def analyze_raster(
        self,
        image_path: str | Path,
        pixels_per_meter: float = 100.0,
        num_floors: int = 1,
        floor_height_m: float = 3.0
    ) -> ArchitecturalProject:
        """
        Analyze a raster floor plan (JPG/PNG/scanned blueprint) using OpenCV.
        Transforms pixel contours into SI-calibrated walls and rooms.
        """
        path = Path(image_path)
        logger.info(f"Analyzing raster architectural drawing: {path.name} @ {pixels_per_meter} px/m")

        pre = RasterPreprocessor(path)
        deskewed, angle = pre.deskew()
        binary = pre.binarize()
        wall_masks = pre.extract_wall_lines(binary)

        calibrator = ScaleCalibrator(pixels_per_meter=pixels_per_meter, is_verified=True)

        # Find external and internal contours
        import cv2
        contours, hierarchy = cv2.findContours(
            wall_masks["combined"], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE
        )

        walls: List[Wall] = []
        rooms: List[Room] = []
        wall_counter = 1
        room_counter = 1

        # Origin at image center or top-left
        ox, oy = 0.0, float(pre.height)

        for cnt in contours:
            # Approximate polygon
            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            area_px = cv2.contourArea(cnt)
            area_sqm = area_px / (pixels_per_meter ** 2)

            # Detect rooms (enclosed loops between 4.0m² and 200.0m²)
            if 4.0 <= area_sqm <= 200.0 and len(approx) >= 4:
                pts = []
                for p in approx:
                    p_flat = np.array(p).flatten()
                    if len(p_flat) >= 2:
                        pts.append(calibrator.point_to_meters(Point2D(x=float(p_flat[0]), y=float(p_flat[1])), origin=Point2D(x=ox, y=oy)))
                if len(pts) >= 3:
                    rooms.append(Room(
                        room_id=f"ROOM_{room_counter:03d}",
                        name=f"Room {room_counter}",
                        boundary_polygon=pts,
                        confidence=0.88,
                        confidence_level=ConfidenceLevel.HIGH
                    ))
                    room_counter += 1

            # Detect wall lines from long contour edges
            if len(approx) >= 2:
                for i in range(len(approx)):
                    p1_coords = np.array(approx[i]).flatten()
                    p2_coords = np.array(approx[(i + 1) % len(approx)]).flatten()
                    if len(p1_coords) < 2 or len(p2_coords) < 2:
                        continue
                    p1_px = Point2D(x=float(p1_coords[0]), y=float(p1_coords[1]))
                    p2_px = Point2D(x=float(p2_coords[0]), y=float(p2_coords[1]))
                    
                    p1_m = calibrator.point_to_meters(p1_px, origin=Point2D(x=ox, y=oy))
                    p2_m = calibrator.point_to_meters(p2_px, origin=Point2D(x=ox, y=oy))

                    L = p1_m.distance_to(p2_m)
                    if L >= 1.0:
                        walls.append(Wall(
                            wall_id=f"WALL_{wall_counter:03d}",
                            start=p1_m,
                            end=p2_m,
                            thickness_m=0.23,
                            height_m=floor_height_m,
                            wall_type=WallType.EXTERIOR if L >= 3.5 else WallType.INTERIOR,
                            confidence=0.85,
                            confidence_level=ConfidenceLevel.HIGH
                        ))
                        wall_counter += 1

        # Create level & building
        footprint_w = round(pre.width / pixels_per_meter, 2)
        footprint_h = round(pre.height / pixels_per_meter, 2)
        footprint_polygon = [
            Point2D(x=0.0, y=0.0),
            Point2D(x=footprint_w, y=0.0),
            Point2D(x=footprint_w, y=footprint_h),
            Point2D(x=0.0, y=footprint_h),
        ]

        levels: List[FloorLevel] = []
        for f_idx in range(max(1, num_floors)):
            elevation = round(f_idx * floor_height_m, 2)
            slab = Slab(
                slab_id=f"SLAB_L{f_idx + 1}_01",
                boundary_polygon=footprint_polygon,
                thickness_m=0.15,
                elevation_m=elevation
            )
            level = FloorLevel(
                level_id=f"lvl_{f_idx + 1}",
                name="Ground Floor" if f_idx == 0 else f"Level {f_idx + 1}",
                elevation_m=elevation,
                floor_to_floor_height_m=floor_height_m,
                default_wall_height_m=floor_height_m,
                walls=walls,
                rooms=rooms,
                slabs=[slab]
            )
            levels.append(level)

        building = Building(name=self.project_name, levels=levels)
        ext = path.suffix.upper().replace(".", "")
        fmt = DrawingFormat.PNG if ext == "PNG" else DrawingFormat.JPG

        project = ArchitecturalProject(
            project_name=self.project_name,
            source_filename=path.name,
            source_format=fmt,
            units=MeasurementUnit.METERS,
            scale_verified=True,
            pixel_scale_ratio=pixels_per_meter,
            building=building,
            metadata={"deskew_angle": angle, "resolution": f"{pre.width}x{pre.height}"}
        )

        out_file = STUDIO_DATA_DIR / f"{project.project_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(project.model_dump_json(indent=2))

        logger.info(f"Successfully analyzed raster plan into ArchitecturalProject {project.project_id}")
        return project
