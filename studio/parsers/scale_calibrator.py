"""
studio.parsers.scale_calibrator
===============================
Interactive Drawing Scale Calibration.
Calculates pixel-to-meter and CAD-unit-to-meter scaling factors
using known dimension lines or user-selected two-point reference lengths.
"""

import math
from typing import Tuple, Dict, Any, Optional
from studio.models.geometry import Point2D
from utils.logging_config import logger


class ScaleCalibrator:
    """
    Manages scale calibration for architectural drawings.
    Ensures extracted geometries translate into exact physical SI units (meters).
    """

    def __init__(self, pixels_per_meter: float = 100.0, is_verified: bool = False):
        self.pixels_per_meter: float = max(0.001, float(pixels_per_meter))
        self.is_verified: bool = is_verified
        self.reference_points: Optional[Tuple[Point2D, Point2D]] = None
        self.reference_length_meters: Optional[float] = None

    def calibrate_from_two_points(
        self,
        p1: Point2D,
        p2: Point2D,
        known_length_meters: float
    ) -> float:
        """
        Calibrate scale given two image pixel points and the known real-world distance in meters.
        Example: User clicks both ends of a 5.0m exterior wall.
        """
        if known_length_meters <= 0:
            raise ValueError(f"Known length must be positive, got {known_length_meters}")

        dx = p2.x - p1.x
        dy = p2.y - p1.y
        pixel_distance = math.hypot(dx, dy)

        if pixel_distance < 1.0:
            raise ValueError("Reference points are too close together to establish a valid scale (< 1px).")

        self.pixels_per_meter = round(pixel_distance / known_length_meters, 4)
        self.is_verified = True
        self.reference_points = (p1, p2)
        self.reference_length_meters = known_length_meters

        logger.info(
            f"Scale calibrated: {pixel_distance:.2f}px = {known_length_meters:.2f}m "
            f"-> {self.pixels_per_meter:.3f} px/m"
        )
        return self.pixels_per_meter

    def pixels_to_meters(self, pixel_val: float) -> float:
        """Convert a pixel distance to physical meters."""
        return round(float(pixel_val) / self.pixels_per_meter, 4)

    def meters_to_pixels(self, meter_val: float) -> float:
        """Convert physical meters to pixel coordinate length."""
        return round(float(meter_val) * self.pixels_per_meter, 2)

    def point_to_meters(self, pt: Point2D, origin: Optional[Point2D] = None) -> Point2D:
        """
        Convert pixel coordinates to SI meter coordinates relative to an origin.
        Y axis is inverted because image raster Y is downwards, CAD/3D Y is upwards.
        """
        ox = origin.x if origin else 0.0
        oy = origin.y if origin else 0.0
        mx = (pt.x - ox) / self.pixels_per_meter
        my = -(pt.y - oy) / self.pixels_per_meter
        return Point2D(x=round(mx, 4), y=round(my, 4))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pixels_per_meter": self.pixels_per_meter,
            "meters_per_pixel": round(1.0 / self.pixels_per_meter, 6),
            "is_verified": self.is_verified,
            "reference_length_meters": self.reference_length_meters,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScaleCalibrator":
        ppm = data.get("pixels_per_meter", 100.0)
        verified = data.get("is_verified", False)
        cal = cls(pixels_per_meter=ppm, is_verified=verified)
        cal.reference_length_meters = data.get("reference_length_meters")
        return cal
