"""
studio.models.geometry
======================
Mathematical 2D and 3D geometric primitives for architectural layout,
CAD entity normalization, and volumetric mesh operations.
"""

from __future__ import annotations
import math
from typing import List, Tuple, Optional
from pydantic import BaseModel, Field


class Point2D(BaseModel):
    """2D coordinate in plan view (meters)."""
    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")

    def distance_to(self, other: Point2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def angle_to(self, other: Point2D) -> float:
        """Return angle in radians from self to other."""
        return math.atan2(other.y - self.y, other.x - self.x)

    def angle_deg_to(self, other: Point2D) -> float:
        """Return angle in degrees [0, 360)."""
        deg = math.degrees(self.angle_to(other))
        return deg % 360.0

    def add(self, dx: float, dy: float) -> Point2D:
        return Point2D(x=round(self.x + dx, 5), y=round(self.y + dy, 5))

    def rotate(self, origin: Point2D, angle_rad: float) -> Point2D:
        """Rotate point around an origin by angle in radians."""
        cos_a = math.cos(angle_rad)
        sin_a = math.sin(angle_rad)
        px = self.x - origin.x
        py = self.y - origin.y
        nx = origin.x + px * cos_a - py * sin_a
        ny = origin.y + px * sin_a + py * cos_a
        return Point2D(x=round(nx, 5), y=round(ny, 5))


class Point3D(BaseModel):
    """3D point in world coordinates (meters)."""
    x: float = Field(..., description="X coordinate in meters")
    y: float = Field(..., description="Y coordinate in meters")
    z: float = Field(..., description="Elevation / Z coordinate in meters")

    def distance_to(self, other: Point3D) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2 +
            (self.z - other.z) ** 2
        )

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def to_point2d(self) -> Point2D:
        return Point2D(x=self.x, y=self.y)


class Vector2D(BaseModel):
    """2D direction vector."""
    dx: float
    dy: float

    @classmethod
    def from_points(cls, start: Point2D, end: Point2D) -> Vector2D:
        return cls(dx=end.x - start.x, dy=end.y - start.y)

    @property
    def length(self) -> float:
        return math.hypot(self.dx, self.dy)

    def normalized(self) -> Vector2D:
        l = self.length
        if l < 1e-9:
            return Vector2D(dx=0.0, dy=0.0)
        return Vector2D(dx=self.dx / l, dy=self.dy / l)

    def perpendicular(self) -> Vector2D:
        """Return normal vector perpendicular to this direction (-dy, dx)."""
        n = self.normalized()
        return Vector2D(dx=-n.dy, dy=n.dx)

    def dot(self, other: Vector2D) -> float:
        return self.dx * other.dx + self.dy * other.dy


class LineSegment2D(BaseModel):
    """2D line segment representing a wall axis, dimension line, or boundary."""
    start: Point2D
    end: Point2D

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def midpoint(self) -> Point2D:
        return Point2D(
            x=round((self.start.x + self.end.x) / 2.0, 5),
            y=round((self.start.y + self.end.y) / 2.0, 5)
        )

    @property
    def angle_rad(self) -> float:
        return self.start.angle_to(self.end)

    @property
    def angle_deg(self) -> float:
        return self.start.angle_deg_to(self.end)

    def vector(self) -> Vector2D:
        return Vector2D.from_points(self.start, self.end)

    def point_at(self, distance_from_start: float) -> Point2D:
        """Return Point2D at given distance along this segment."""
        v = self.vector().normalized()
        return Point2D(
            x=round(self.start.x + v.dx * distance_from_start, 5),
            y=round(self.start.y + v.dy * distance_from_start, 5)
        )

    def offset(self, distance: float) -> LineSegment2D:
        """Offset segment perpendicularly by distance (positive = left)."""
        perp = self.vector().perpendicular()
        s = Point2D(x=round(self.start.x + perp.dx * distance, 5), y=round(self.start.y + perp.dy * distance, 5))
        e = Point2D(x=round(self.end.x + perp.dx * distance, 5), y=round(self.end.y + perp.dy * distance, 5))
        return LineSegment2D(start=s, end=e)

    def distance_to_point(self, pt: Point2D) -> float:
        """Shortest distance from point to this segment."""
        l2 = (self.end.x - self.start.x) ** 2 + (self.end.y - self.start.y) ** 2
        if l2 < 1e-9:
            return self.start.distance_to(pt)
        # Project pt onto segment, clamp t to [0, 1]
        t = ((pt.x - self.start.x) * (self.end.x - self.start.x) + (pt.y - self.start.y) * (self.end.y - self.start.y)) / l2
        t = max(0.0, min(1.0, t))
        proj = Point2D(
            x=self.start.x + t * (self.end.x - self.start.x),
            y=self.start.y + t * (self.end.y - self.start.y)
        )
        return pt.distance_to(proj)


class BoundingBox2D(BaseModel):
    """Axis-aligned bounding box."""
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @classmethod
    def from_points(cls, points: List[Point2D]) -> BoundingBox2D:
        if not points:
            return cls(min_x=0.0, min_y=0.0, max_x=0.0, max_y=0.0)
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return cls(min_x=min(xs), min_y=min(ys), max_x=max(xs), max_y=max(ys))

    @property
    def width(self) -> float:
        return max(0.0, self.max_x - self.min_x)

    @property
    def height(self) -> float:
        return max(0.0, self.max_y - self.min_y)

    @property
    def area(self) -> float:
        return round(self.width * self.height, 4)

    @property
    def center(self) -> Point2D:
        return Point2D(
            x=round((self.min_x + self.max_x) / 2.0, 5),
            y=round((self.min_y + self.max_y) / 2.0, 5)
        )

    def contains_point(self, pt: Point2D, tolerance: float = 0.0) -> bool:
        return (
            (self.min_x - tolerance) <= pt.x <= (self.max_x + tolerance) and
            (self.min_y - tolerance) <= pt.y <= (self.max_y + tolerance)
        )

    def overlaps(self, other: BoundingBox2D) -> bool:
        return not (
            self.max_x < other.min_x or self.min_x > other.max_x or
            self.max_y < other.min_y or self.min_y > other.max_y
        )


def polygon_area(points: List[Point2D]) -> float:
    """Calculate signed polygon area using Shoelace formula (positive = CCW)."""
    n = len(points)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += points[i].x * points[j].y
        area -= points[j].x * points[i].y
    return abs(area) / 2.0


def polygon_perimeter(points: List[Point2D]) -> float:
    """Calculate total boundary perimeter of polygon."""
    n = len(points)
    if n < 2:
        return 0.0
    p = 0.0
    for i in range(n):
        j = (i + 1) % n
        p += points[i].distance_to(points[j])
    return round(p, 4)
