"""
studio.parsers.dxf_parser
=========================
Advanced DXF Architectural Parser.
Reads AutoCAD / BricsCAD / LibreCAD DXF drawings (R12 through 2018+),
extracts geometric primitives (LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, TEXT, MTEXT, DIMENSION),
and heuristically maps CAD layers to BIM architectural categories.
"""

import math
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import ezdxf
from ezdxf.document import Drawing
from ezdxf.entities import Line, LWPolyline, Polyline, Arc, Circle, Text, MText, Dimension

from studio.models.geometry import Point2D, LineSegment2D, BoundingBox2D
from studio.models.project import MeasurementUnit
from utils.logging_config import logger

# Keyword dictionaries for CAD layer classification
LAYER_KEYWORDS: Dict[str, List[str]] = {
    "WALL": ["wall", "mur", "paroi", "w-", "a-wall", "walls", "arch-wall", "exterior", "interior", "perimeter", "cloture"],
    "DOOR": ["door", "porte", "dr", "a-door", "doors", "swing", "porte_battante"],
    "WINDOW": ["window", "fenetre", "win", "glaz", "a-glaz", "a-flor-glaz", "glass", "fen", "vitrage"],
    "COLUMN": ["column", "col", "poteau", "s-cols", "pilier", "pillar", "structural_col"],
    "STAIR": ["stair", "escalier", "str", "a-flr-str", "steps", "marche"],
    "ROOM": ["room", "piece", "space", "area", "zone", "local"],
    "DIMENSION": ["dim", "cotation", "measure", "dimension", "cot"],
    "ANNOTATION": ["text", "txt", "label", "anno", "tag", "titre", "nom"],
    "SLAB": ["slab", "dalle", "floor", "plancher", "balcony_slab"],
}

# AutoCAD $INSUNITS mapping to SI meters multiplier
# 1 = Inches, 2 = Feet, 4 = Millimeters, 5 = Centimeters, 6 = Meters
INSUNITS_TO_METERS: Dict[int, float] = {
    1: 0.0254,       # Inches
    2: 0.3048,       # Feet
    3: 0.9144,       # Miles -> Yards
    4: 0.001,        # Millimeters
    5: 0.01,         # Centimeters
    6: 1.0,          # Meters
    7: 1000.0,       # Kilometers
}


class DXFParser:
    """
    Parses DXF files into structured architectural entities.
    Preserves layer names, original coordinates, and performs semantic entity grouping.
    """

    def __init__(self, filepath: str | Path):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"DXF file not found: {self.filepath}")

        self.doc: Drawing = ezdxf.readfile(str(self.filepath))
        self.modelspace = self.doc.modelspace()
        self.unit_scale: float = self._detect_unit_scale()

    def _detect_unit_scale(self) -> float:
        """Detect drawing units from $INSUNITS header or default to 1.0 (meters)."""
        try:
            insunits = self.doc.header.get("$INSUNITS", 0)
            if insunits in INSUNITS_TO_METERS:
                scale = INSUNITS_TO_METERS[insunits]
                logger.info(f"DXF $INSUNITS detected: {insunits} -> multiplier to meters = {scale}")
                return scale
        except Exception as e:
            logger.warning(f"Failed to read DXF $INSUNITS header: {e}")
        return 1.0  # Default assumption: 1 CAD unit = 1 meter

    @staticmethod
    def classify_layer(layer_name: str) -> str:
        """Heuristically assign a CAD layer name to an architectural category."""
        clean = layer_name.lower().strip()
        for category, keywords in LAYER_KEYWORDS.items():
            for kw in keywords:
                if kw in clean:
                    return category
        return "UNKNOWN"

    def get_layer_table(self) -> Dict[str, Dict[str, Any]]:
        """Return all layers in drawing with entity counts and predicted category."""
        layers_info: Dict[str, Dict[str, Any]] = {}
        for layer in self.doc.layers:
            layers_info[layer.dxf.name] = {
                "name": layer.dxf.name,
                "color": layer.color,
                "is_off": layer.is_off(),
                "is_locked": layer.is_locked(),
                "predicted_category": self.classify_layer(layer.dxf.name),
                "entity_count": 0,
            }
        
        # Count entities per layer
        for e in self.modelspace:
            lay = e.dxf.layer
            if lay in layers_info:
                layers_info[lay]["entity_count"] += 1
            else:
                layers_info[lay] = {
                    "name": lay,
                    "color": 7,
                    "is_off": False,
                    "is_locked": False,
                    "predicted_category": self.classify_layer(lay),
                    "entity_count": 1,
                }
        return layers_info

    def extract_entities(self) -> Dict[str, Any]:
        """
        Extract all geometric primitives, converted to SI meters,
        indexed by layer and classified into architectural categories.
        """
        lines: List[Dict[str, Any]] = []
        polylines: List[Dict[str, Any]] = []
        arcs: List[Dict[str, Any]] = []
        circles: List[Dict[str, Any]] = []
        texts: List[Dict[str, Any]] = []
        dimensions: List[Dict[str, Any]] = []

        scale = self.unit_scale
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = float("-inf"), float("-inf")

        def update_bounds(px: float, py: float):
            nonlocal min_x, min_y, max_x, max_y
            min_x = min(min_x, px)
            min_y = min(min_y, py)
            max_x = max(max_x, px)
            max_y = max(max_y, py)

        for e in self.modelspace:
            layer = e.dxf.layer
            cat = self.classify_layer(layer)

            # LINE
            if e.dxftype() == "LINE":
                sx, sy = e.dxf.start.x * scale, e.dxf.start.y * scale
                ex, ey = e.dxf.end.x * scale, e.dxf.end.y * scale
                update_bounds(sx, sy)
                update_bounds(ex, ey)
                lines.append({
                    "layer": layer,
                    "category": cat,
                    "start": {"x": round(sx, 4), "y": round(sy, 4)},
                    "end": {"x": round(ex, 4), "y": round(ey, 4)},
                    "length_m": round(math.hypot(ex - sx, ey - sy), 4),
                })

            # LWPOLYLINE
            elif e.dxftype() == "LWPOLYLINE":
                pts: List[Dict[str, float]] = []
                for pt in e.get_points(format="xy"):
                    x, y = pt[0] * scale, pt[1] * scale
                    update_bounds(x, y)
                    pts.append({"x": round(x, 4), "y": round(y, 4)})
                
                polylines.append({
                    "layer": layer,
                    "category": cat,
                    "points": pts,
                    "is_closed": bool(e.closed),
                })

            # POLYLINE (2D / 3D legacy)
            elif e.dxftype() == "POLYLINE":
                pts = []
                for v in e.vertices:
                    x, y = v.dxf.location.x * scale, v.dxf.location.y * scale
                    update_bounds(x, y)
                    pts.append({"x": round(x, 4), "y": round(y, 4)})
                polylines.append({
                    "layer": layer,
                    "category": cat,
                    "points": pts,
                    "is_closed": bool(e.is_closed),
                })

            # ARC (often represents door swings)
            elif e.dxftype() == "ARC":
                cx, cy = e.dxf.center.x * scale, e.dxf.center.y * scale
                r = e.dxf.radius * scale
                update_bounds(cx - r, cy - r)
                update_bounds(cx + r, cy + r)
                arcs.append({
                    "layer": layer,
                    "category": cat if cat != "UNKNOWN" else "DOOR",
                    "center": {"x": round(cx, 4), "y": round(cy, 4)},
                    "radius_m": round(r, 4),
                    "start_angle_deg": round(e.dxf.start_angle, 2),
                    "end_angle_deg": round(e.dxf.end_angle, 2),
                })

            # CIRCLE (often represents columns or markers)
            elif e.dxftype() == "CIRCLE":
                cx, cy = e.dxf.center.x * scale, e.dxf.center.y * scale
                r = e.dxf.radius * scale
                update_bounds(cx - r, cy - r)
                update_bounds(cx + r, cy + r)
                circles.append({
                    "layer": layer,
                    "category": cat if cat != "UNKNOWN" else "COLUMN",
                    "center": {"x": round(cx, 4), "y": round(cy, 4)},
                    "radius_m": round(r, 4),
                })

            # TEXT & MTEXT
            elif e.dxftype() in ("TEXT", "MTEXT"):
                txt_val = e.dxf.text if hasattr(e.dxf, "text") else ""
                ins_x = e.dxf.insert.x * scale if hasattr(e.dxf, "insert") else 0.0
                ins_y = e.dxf.insert.y * scale if hasattr(e.dxf, "insert") else 0.0
                update_bounds(ins_x, ins_y)
                texts.append({
                    "layer": layer,
                    "category": cat,
                    "text": txt_val.strip(),
                    "position": {"x": round(ins_x, 4), "y": round(ins_y, 4)},
                    "height_m": round(e.dxf.height * scale, 3) if hasattr(e.dxf, "height") else 0.25,
                })

        # Calculate bounding box
        bbox = {
            "min_x": round(min_x, 4) if min_x != float("inf") else 0.0,
            "min_y": round(min_y, 4) if min_y != float("inf") else 0.0,
            "max_x": round(max_x, 4) if max_x != float("-inf") else 0.0,
            "max_y": round(max_y, 4) if max_y != float("-inf") else 0.0,
            "width_m": round(max(0.0, max_x - min_x), 4) if min_x != float("inf") else 0.0,
            "height_m": round(max(0.0, max_y - min_y), 4) if min_y != float("inf") else 0.0,
        }

        return {
            "source_file": self.filepath.name,
            "unit_scale_applied": self.unit_scale,
            "bounding_box": bbox,
            "layers": self.get_layer_table(),
            "lines": lines,
            "polylines": polylines,
            "arcs": arcs,
            "circles": circles,
            "texts": texts,
            "total_entity_count": len(lines) + len(polylines) + len(arcs) + len(circles) + len(texts),
        }
