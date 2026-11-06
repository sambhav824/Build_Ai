"""
tests.test_studio_parsers
=========================
Unit tests for Milestone 2: Drawing Ingestion & Scale Calibration.
Tests:
- ScaleCalibrator: two-point distance to SI meters calibration.
- DXFParser: entity extraction, unit scaling, layer classification.
- DWGHandler: converter detection and header validation.
- RasterPreprocessor: OpenCV deskewing, binarization, and morphological wall extraction.
"""

import tempfile
from pathlib import Path
import pytest
import numpy as np
import cv2
import ezdxf

from studio.models.geometry import Point2D
from studio.parsers.scale_calibrator import ScaleCalibrator
from studio.parsers.dxf_parser import DXFParser
from studio.parsers.dwg_handler import DWGHandler
from studio.parsers.raster_preprocessor import RasterPreprocessor


def test_scale_calibrator():
    cal = ScaleCalibrator()
    # 500 pixels corresponds to 5.0 meters -> 100 pixels per meter
    p1 = Point2D(x=100.0, y=200.0)
    p2 = Point2D(x=600.0, y=200.0)
    ppm = cal.calibrate_from_two_points(p1, p2, 5.0)

    assert ppm == 100.0
    assert cal.is_verified is True
    assert cal.pixels_to_meters(250.0) == 2.5
    assert cal.meters_to_pixels(3.5) == 350.0

    # Test point conversion with inverted Y
    meter_pt = cal.point_to_meters(Point2D(x=200, y=100), origin=Point2D(x=0, y=0))
    assert meter_pt.x == 2.0
    assert meter_pt.y == -1.0


def test_dxf_parser_with_synthetic_cad():
    with tempfile.TemporaryDirectory() as tmpdir:
        dxf_path = Path(tmpdir) / "test_arch_drawing.dxf"

        # Create DXF with ezdxf
        doc = ezdxf.new("R2010")
        doc.header["$INSUNITS"] = 6  # Meters
        msp = doc.modelspace()

        # Add layers
        doc.layers.new(name="A-WALL-EXT", dxfattribs={"color": 1})
        doc.layers.new(name="A-DOOR", dxfattribs={"color": 2})

        # Add entities
        msp.add_line((0, 0), (10, 0), dxfattribs={"layer": "A-WALL-EXT"})
        msp.add_line((10, 0), (10, 8), dxfattribs={"layer": "A-WALL-EXT"})
        msp.add_arc(center=(2, 0), radius=0.9, start_angle=0, end_angle=90, dxfattribs={"layer": "A-DOOR"})
        msp.add_text("Living Room", dxfattribs={"layer": "A-WALL-EXT"}).set_placement((5, 4))

        doc.saveas(str(dxf_path))

        # Parse with DXFParser
        parser = DXFParser(dxf_path)
        data = parser.extract_entities()

        assert data["unit_scale_applied"] == 1.0
        assert len(data["lines"]) == 2
        assert len(data["arcs"]) == 1
        assert len(data["texts"]) == 1
        assert data["lines"][0]["category"] == "WALL"
        assert data["arcs"][0]["category"] == "DOOR"
        assert data["bounding_box"]["width_m"] >= 10.0


def test_dwg_handler_fallback():
    with tempfile.TemporaryDirectory() as tmpdir:
        fake_dwg = Path(tmpdir) / "sample.dwg"
        # Write dummy AC1027 header
        fake_dwg.write_bytes(b"AC1027" + b"\x00" * 100)

        handler = DWGHandler(fake_dwg)
        header_info = handler.inspect_dwg_header()
        assert "AutoCAD 2013" in header_info["version"]

        if not handler.is_converter_available():
            with pytest.raises(RuntimeError) as exc_info:
                handler.convert_to_dxf()
            assert "ODA File Converter" in str(exc_info.value)


def test_raster_preprocessor():
    with tempfile.TemporaryDirectory() as tmpdir:
        img_path = Path(tmpdir) / "floorplan_test.png"

        # Generate synthetic 400x400 white canvas with a black rectangle representing walls
        canvas = np.ones((400, 400, 3), dtype=np.uint8) * 255
        cv2.rectangle(canvas, (50, 50), (350, 350), (0, 0, 0), thickness=6)
        cv2.imwrite(str(img_path), canvas)

        pre = RasterPreprocessor(img_path)
        assert pre.width == 400
        assert pre.height == 400

        gray = pre.grayscale()
        assert gray.shape == (400, 400)

        binary = pre.binarize(invert=True)
        # Rectangular walls should be white (255) in binary
        assert np.sum(binary == 255) > 0

        wall_masks = pre.extract_wall_lines(binary, min_wall_length_px=30)
        assert "combined" in wall_masks
        assert np.sum(wall_masks["combined"] == 255) > 0
