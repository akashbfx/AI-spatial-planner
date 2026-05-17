"""
Daylight analysis module — sun orientation and daylight comfort scoring.
"""

import math
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
import numpy as np


class DaylightAnalyzer:
    """Analyzes daylight conditions based on sun orientation and window positions."""

    # Sun penetration depth multipliers by orientation quality
    ORIENTATION_QUALITY = {
        "direct": 1.0,    # Window faces sun directly
        "oblique": 0.6,   # Window at ~45° to sun
        "parallel": 0.3,  # Window parallel to sun direction
        "opposite": 0.1,  # Window faces away from sun
    }

    def __init__(self, room_geometry, sun_orientation=180, daylight_priority="medium"):
        """
        Args:
            room_geometry: RoomGeometry instance
            sun_orientation: Compass bearing of sun direction (0=N, 90=E, 180=S, 270=W)
            daylight_priority: "low", "medium", "high"
        """
        self.room = room_geometry
        self.sun_orientation = sun_orientation
        self.daylight_priority = daylight_priority

        # Sun direction vector (pointing from sun into room)
        self.sun_vector = self._bearing_to_vector(sun_orientation)

        # Priority multiplier
        self._priority_mult = {"low": 0.5, "medium": 1.0, "high": 1.5}.get(
            daylight_priority, 1.0
        )

        # Pre-compute daylight zones
        self._daylight_zones = None
        self._daylight_map = None

    def _bearing_to_vector(self, bearing):
        """Convert compass bearing to unit vector (in screen coords: x=east, y=south)."""
        rad = math.radians(bearing)
        return (math.sin(rad), math.cos(rad))

    def _get_window_sun_quality(self, window):
        """Determine how well a window is oriented toward the sun."""
        wi = window.wall_index
        if wi >= len(self.room.walls):
            return "parallel"

        start, end = self.room.walls[wi]
        # Wall normal (inward)
        wx = end[0] - start[0]
        wy = end[1] - start[1]
        wall_len = math.hypot(wx, wy)
        if wall_len == 0:
            return "parallel"

        # Inward normal
        nx = -wy / wall_len
        ny = wx / wall_len

        # Dot product with sun vector
        dot = nx * self.sun_vector[0] + ny * self.sun_vector[1]

        if dot > 0.7:
            return "direct"
        elif dot > 0.3:
            return "oblique"
        elif dot > -0.3:
            return "parallel"
        else:
            return "opposite"

    @property
    def daylight_zones(self):
        """Get all daylight zones with quality ratings."""
        if self._daylight_zones is None:
            self._daylight_zones = []
            raw_zones = self.room.get_window_daylight_zones(primary=200, secondary=400)

            for z in raw_zones:
                quality = self._get_window_sun_quality(z["window"])
                quality_mult = self.ORIENTATION_QUALITY[quality]

                self._daylight_zones.append({
                    "polygon": z["polygon"],
                    "zone_type": z["zone"],
                    "quality": quality,
                    "quality_score": quality_mult,
                    "window_wall_index": z["window"].wall_index,
                })

        return self._daylight_zones

    def score_position(self, x, y, category="work_desk"):
        """Score a position for daylight comfort.

        Args:
            x, y: Position in cm
            category: Furniture category

        Returns:
            Score from 0 to 100
        """
        point = Point(x, y)

        # Category preferences for daylight
        category_daylight_pref = {
            "work_desk": 0.8,
            "shared_table": 0.7,
            "meeting_table": 0.5,
            "chair": 0.6,
            "storage": 0.1,
            "collaborative_seating": 0.6,
            "lounge": 0.9,
        }

        pref = category_daylight_pref.get(category, 0.5)
        best_score = 0

        for zone in self.daylight_zones:
            if zone["polygon"].contains(point):
                zone_base = 100 if zone["zone_type"] == "primary" else 60
                score = zone_base * zone["quality_score"] * pref
                best_score = max(best_score, score)
            else:
                # Partial score for nearby positions
                dist = zone["polygon"].distance(point)
                if dist < 200:
                    falloff = max(0, 1 - dist / 200)
                    zone_base = 80 if zone["zone_type"] == "primary" else 40
                    score = zone_base * zone["quality_score"] * pref * falloff
                    best_score = max(best_score, score)

        # If no windows or storage, return neutral score
        if not self.daylight_zones:
            return 50
        if pref < 0.2:
            return 70  # Storage doesn't care much

        return min(100, best_score * self._priority_mult)

    def score_layout(self, placements, furniture_pieces):
        """Score entire layout for daylight comfort.

        Returns:
            Score 0-100 and per-piece scores
        """
        if not self.daylight_zones or not placements:
            return {"overall": 50, "per_piece": []}

        scores = []
        for piece, (x, y, rot) in zip(furniture_pieces, placements):
            score = self.score_position(x, y, piece.category)
            scores.append({
                "piece_id": piece.id,
                "score": round(score, 1),
                "category": piece.category,
            })

        # Weighted average (weight by daylight preference importance)
        total_weight = 0
        weighted_sum = 0
        for piece, s in zip(furniture_pieces, scores):
            weight = 1.0
            if piece.category in ("work_desk", "lounge"):
                weight = 2.0
            elif piece.category == "storage":
                weight = 0.3
            weighted_sum += s["score"] * weight
            total_weight += weight

        overall = weighted_sum / total_weight if total_weight > 0 else 50

        return {
            "overall": round(min(100, overall), 1),
            "per_piece": scores,
            "sun_orientation": self.sun_orientation,
            "daylight_priority": self.daylight_priority,
        }

    def get_daylight_map(self):
        """Generate a grid-based daylight intensity map for visualization.

        Returns:
            dict with grid data for frontend rendering
        """
        bounds = self.room.bounds
        grid_step = 50  # 50cm resolution
        minx, miny, maxx, maxy = bounds

        grid = []
        for y in np.arange(miny, maxy, grid_step):
            for x in np.arange(minx, maxx, grid_step):
                if self.room.point_in_room(x, y):
                    score = self.score_position(x, y, "work_desk")
                    grid.append({
                        "x": float(x),
                        "y": float(y),
                        "intensity": round(score / 100, 2),
                    })

        return {
            "grid": grid,
            "grid_step": grid_step,
            "bounds": {"minx": minx, "miny": miny, "maxx": maxx, "maxy": maxy},
        }
