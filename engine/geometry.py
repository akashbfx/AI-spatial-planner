"""
Room geometry module — handles room shapes, walls, doors, windows using Shapely.
"""

import math
from shapely.geometry import Polygon, LineString, Point, box
from shapely.affinity import rotate, translate
from shapely.ops import unary_union
import numpy as np


class Door:
    """Represents a door in the room."""

    def __init__(self, position, width=90, wall_index=0, swing="inward"):
        self.position = position  # [x, y] center point on wall
        self.width = width  # cm
        self.wall_index = wall_index
        self.swing = swing  # "inward" or "outward"

    def get_clearance_zone(self, wall_start, wall_end, clearance=100):
        """Generate clearance polygon in front of the door."""
        wx = wall_end[0] - wall_start[0]
        wy = wall_end[1] - wall_start[1]
        wall_len = math.hypot(wx, wy)
        if wall_len == 0:
            return Polygon()

        # Unit vectors
        ux, uy = wx / wall_len, wy / wall_len  # along wall
        nx, ny = -uy, ux  # perpendicular (inward normal)

        cx, cy = self.position
        hw = self.width / 2

        # Clearance rectangle perpendicular to wall
        p1 = (cx - ux * hw, cy - uy * hw)
        p2 = (cx + ux * hw, cy + uy * hw)
        p3 = (cx + ux * hw + nx * clearance, cy + uy * hw + ny * clearance)
        p4 = (cx - ux * hw + nx * clearance, cy - uy * hw + ny * clearance)

        poly = Polygon([p1, p2, p3, p4])
        if poly.is_valid and poly.area > 0:
            return poly

        # Also create swing arc zone
        swing_poly = Point(cx, cy).buffer(self.width).intersection(
            Polygon([
                (cx, cy),
                (cx + nx * self.width, cy + ny * self.width),
                (cx + nx * self.width + ux * self.width, cy + ny * self.width + uy * self.width),
                (cx + ux * self.width, cy + uy * self.width)
            ])
        )
        return unary_union([poly, swing_poly]) if swing_poly.is_valid else poly

    def to_dict(self):
        return {
            "position": self.position,
            "width": self.width,
            "wall_index": self.wall_index,
            "swing": self.swing,
        }


class Window:
    """Represents a window in the room."""

    def __init__(self, position, width=120, wall_index=0, sill_height=90, head_height=210):
        self.position = position  # [x, y] center point on wall
        self.width = width  # cm
        self.wall_index = wall_index
        self.sill_height = sill_height  # cm from floor
        self.head_height = head_height  # cm from floor

    def get_daylight_zones(self, wall_start, wall_end, primary=200, secondary=400):
        """Generate daylight penetration zones from this window."""
        wx = wall_end[0] - wall_start[0]
        wy = wall_end[1] - wall_start[1]
        wall_len = math.hypot(wx, wy)
        if wall_len == 0:
            return []

        ux, uy = wx / wall_len, wy / wall_len
        nx, ny = -uy, ux  # inward normal

        cx, cy = self.position
        hw = self.width / 2

        zones = []
        # Daylight spreads at ~45 degree angle from window edges
        spread_factor = 1.5

        for depth, label in [(primary, "primary"), (secondary, "secondary")]:
            spread = hw + depth * (spread_factor - 1)
            p1 = (cx - ux * hw, cy - uy * hw)
            p2 = (cx + ux * hw, cy + uy * hw)
            p3 = (cx + ux * spread + nx * depth, cy + uy * spread + ny * depth)
            p4 = (cx - ux * spread + nx * depth, cy - uy * spread + ny * depth)
            poly = Polygon([p1, p2, p3, p4])
            if poly.is_valid and poly.area > 0:
                zones.append({"zone": label, "polygon": poly, "depth": depth})

        return zones

    def to_dict(self):
        return {
            "position": self.position,
            "width": self.width,
            "wall_index": self.wall_index,
            "sill_height": self.sill_height,
            "head_height": self.head_height,
        }


class RoomGeometry:
    """Represents the complete room geometry."""

    def __init__(self, vertices, doors=None, windows=None):
        """
        Args:
            vertices: List of [x, y] coordinates forming the room boundary (cm).
            doors: List of Door objects.
            windows: List of Window objects.
        """
        self.vertices = [tuple(v) for v in vertices]
        self.doors = doors or []
        self.windows = windows or []

        # Create Shapely polygon
        if len(self.vertices) >= 3:
            self.polygon = Polygon(self.vertices)
            if not self.polygon.is_valid:
                self.polygon = self.polygon.buffer(0)
        else:
            self.polygon = Polygon()

        self._walls = None
        self._wall_orientations = None

    @property
    def walls(self):
        """Get wall segments as list of ((x1,y1), (x2,y2))."""
        if self._walls is None:
            self._walls = []
            n = len(self.vertices)
            for i in range(n):
                start = self.vertices[i]
                end = self.vertices[(i + 1) % n]
                self._walls.append((start, end))
        return self._walls

    @property
    def wall_orientations(self):
        """Get cardinal orientation of each wall."""
        if self._wall_orientations is None:
            self._wall_orientations = []
            for start, end in self.walls:
                dx = end[0] - start[0]
                dy = end[1] - start[1]
                angle = math.degrees(math.atan2(dy, dx)) % 360
                if 45 <= angle < 135:
                    orient = "S"  # wall faces south (runs E-W)
                elif 135 <= angle < 225:
                    orient = "W"
                elif 225 <= angle < 315:
                    orient = "N"
                else:
                    orient = "E"
                self._wall_orientations.append(orient)
        return self._wall_orientations

    @property
    def area(self):
        """Room area in square cm."""
        return self.polygon.area

    @property
    def area_sqm(self):
        """Room area in square meters."""
        return self.area / 10000

    @property
    def perimeter(self):
        """Room perimeter in cm."""
        return self.polygon.length

    @property
    def bounds(self):
        """(minx, miny, maxx, maxy) of the room."""
        return self.polygon.bounds

    @property
    def centroid(self):
        """Room centroid as (x, y)."""
        c = self.polygon.centroid
        return (c.x, c.y)

    def wall_length(self, index):
        """Get length of a specific wall."""
        start, end = self.walls[index]
        return math.hypot(end[0] - start[0], end[1] - start[1])

    def get_door_clearance_zones(self, clearance=100):
        """Get all door clearance zones as Shapely polygons."""
        zones = []
        for door in self.doors:
            wi = door.wall_index
            if 0 <= wi < len(self.walls):
                start, end = self.walls[wi]
                zone = door.get_clearance_zone(start, end, clearance)
                if zone.is_valid and not zone.is_empty:
                    # Clip to room interior
                    clipped = zone.intersection(self.polygon)
                    if clipped.is_valid and not clipped.is_empty:
                        zones.append(clipped)
        return zones

    def get_window_daylight_zones(self, primary=200, secondary=400):
        """Get all window daylight zones."""
        all_zones = []
        for window in self.windows:
            wi = window.wall_index
            if 0 <= wi < len(self.walls):
                start, end = self.walls[wi]
                zones = window.get_daylight_zones(start, end, primary, secondary)
                for z in zones:
                    clipped_poly = z["polygon"].intersection(self.polygon)
                    if clipped_poly.is_valid and not clipped_poly.is_empty:
                        all_zones.append({
                            "zone": z["zone"],
                            "polygon": clipped_poly,
                            "window": window,
                        })
        return all_zones

    def get_usable_area(self, corridor_width=90):
        """Calculate usable area after subtracting door clearances."""
        door_zones = self.get_door_clearance_zones()
        if not door_zones:
            return self.polygon
        exclusion = unary_union(door_zones)
        usable = self.polygon.difference(exclusion)
        return usable if usable.is_valid else self.polygon

    def get_wall_adjacent_zones(self, depth=60):
        """Get zones adjacent to walls (preferred for desks/storage)."""
        zones = []
        for start, end in self.walls:
            wall_line = LineString([start, end])
            buffer = wall_line.buffer(depth, single_sided=True)
            clipped = buffer.intersection(self.polygon)
            if clipped.is_valid and not clipped.is_empty:
                zones.append(clipped)
        return zones

    def point_in_room(self, x, y):
        """Check if a point is inside the room."""
        return self.polygon.contains(Point(x, y))

    def to_dict(self):
        return {
            "vertices": [list(v) for v in self.vertices],
            "doors": [d.to_dict() for d in self.doors],
            "windows": [w.to_dict() for w in self.windows],
            "area_sqm": round(self.area_sqm, 2),
            "perimeter_cm": round(self.perimeter, 1),
            "wall_orientations": self.wall_orientations,
        }

    @classmethod
    def from_dict(cls, data):
        """Create RoomGeometry from a dictionary."""
        doors = []
        for d in data.get("doors", []):
            doors.append(Door(
                position=d["position"],
                width=d.get("width", 90),
                wall_index=d.get("wall_index", 0),
                swing=d.get("swing", "inward"),
            ))

        windows = []
        for w in data.get("windows", []):
            windows.append(Window(
                position=w["position"],
                width=w.get("width", 120),
                wall_index=w.get("wall_index", 0),
                sill_height=w.get("sill_height", 90),
                head_height=w.get("head_height", 210),
            ))

        return cls(
            vertices=data.get("vertices", data.get("walls", [])),
            doors=doors,
            windows=windows,
        )
