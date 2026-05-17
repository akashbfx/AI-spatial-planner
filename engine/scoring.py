"""
Multi-criteria layout scoring engine.
"""

import math
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union
import numpy as np


class LayoutScorer:
    """Scores layouts on 4 axes: space efficiency, usability, daylight, movement flow."""

    def __init__(self, room_geometry, daylight_analyzer=None, weights=None):
        self.room = room_geometry
        self.daylight = daylight_analyzer
        self.weights = weights or {
            "space_efficiency": 0.25,
            "usability": 0.25,
            "daylight_comfort": 0.25,
            "movement_flow": 0.25,
        }

    def score_space_efficiency(self, placements, furniture_pieces):
        """Score how efficiently space is used (0-100).

        Considers:
        - Ratio of furnished area to total area
        - Wasted pocket spaces
        - Even distribution
        """
        if not placements:
            return 0

        room_area = self.room.polygon.area
        furniture_polys = []

        for piece, (x, y, rot) in zip(furniture_pieces, placements):
            poly = piece.get_polygon(x, y, rot)
            if poly.is_valid:
                furniture_polys.append(poly)

        if not furniture_polys:
            return 0

        furniture_union = unary_union(furniture_polys)
        furnished_area = furniture_union.area
        utilization = furnished_area / room_area

        # Ideal utilization for coworking: 35-55%
        if utilization < 0.15:
            efficiency_score = utilization / 0.15 * 40
        elif utilization <= 0.55:
            efficiency_score = 40 + (utilization - 0.15) / 0.40 * 50
        elif utilization <= 0.70:
            efficiency_score = 90 - (utilization - 0.55) / 0.15 * 20
        else:
            efficiency_score = max(0, 70 - (utilization - 0.70) / 0.30 * 70)

        # Bonus for even distribution (check quadrant balance)
        cx, cy = self.room.centroid
        quadrant_areas = [0, 0, 0, 0]
        for poly in furniture_polys:
            pc = poly.centroid
            qi = (0 if pc.x < cx else 1) + (0 if pc.y < cy else 2)
            quadrant_areas[qi] += poly.area

        total = sum(quadrant_areas) or 1
        fractions = [a / total for a in quadrant_areas]
        balance_score = 1 - np.std(fractions) * 4  # penalize imbalance
        balance_score = max(0, min(1, balance_score))

        final = efficiency_score * 0.7 + balance_score * 30

        return round(min(100, max(0, final)), 1)

    def score_usability(self, placements, furniture_pieces):
        """Score layout usability (0-100).

        Considers:
        - Ergonomic spacing between workstations
        - Functional grouping (similar categories near each other)
        - Adjacency logic
        """
        if not placements:
            return 0

        n = len(placements)
        if n == 1:
            return 70

        # Ergonomic spacing score
        spacing_score = 100
        spacing_violations = 0
        min_spacing = 140  # cm

        desk_types = {"work_desk", "shared_table"}

        for i in range(n):
            for j in range(i + 1, n):
                if (furniture_pieces[i].category in desk_types and
                    furniture_pieces[j].category in desk_types):
                    xi, yi, _ = placements[i]
                    xj, yj, _ = placements[j]
                    dist = math.hypot(xi - xj, yi - yj)
                    if dist < min_spacing and dist > 0:
                        spacing_violations += 1
                        spacing_score -= (min_spacing - dist) / min_spacing * 15

        spacing_score = max(0, spacing_score)

        # Functional grouping score — similar categories should cluster
        category_positions = {}
        for piece, (x, y, _) in zip(furniture_pieces, placements):
            if piece.category not in category_positions:
                category_positions[piece.category] = []
            category_positions[piece.category].append((x, y))

        grouping_score = 100
        for cat, positions in category_positions.items():
            if len(positions) < 2:
                continue
            piece = next(p for p in furniture_pieces if p.category == cat)
            if piece.group_affinity > 0.5:
                # High affinity items should be close
                dists = []
                for i in range(len(positions)):
                    for j in range(i + 1, len(positions)):
                        d = math.hypot(positions[i][0] - positions[j][0],
                                       positions[i][1] - positions[j][1])
                        dists.append(d)
                avg_dist = np.mean(dists) if dists else 0
                room_diag = math.hypot(
                    self.room.bounds[2] - self.room.bounds[0],
                    self.room.bounds[3] - self.room.bounds[1]
                )
                spread = avg_dist / (room_diag or 1)
                if spread > 0.5:
                    grouping_score -= piece.group_affinity * 20

        grouping_score = max(0, grouping_score)

        # Adjacency logic — meeting tables should have chairs nearby
        adjacency_score = 100
        meeting_positions = [(x, y) for p, (x, y, _) in zip(furniture_pieces, placements)
                           if p.category == "meeting_table"]
        chair_positions = [(x, y) for p, (x, y, _) in zip(furniture_pieces, placements)
                         if p.category == "chair"]

        for mx, my in meeting_positions:
            nearby_chairs = sum(
                1 for cx, cy in chair_positions
                if math.hypot(mx - cx, my - cy) < 200
            )
            if nearby_chairs == 0 and chair_positions:
                adjacency_score -= 20

        adjacency_score = max(0, adjacency_score)

        final = spacing_score * 0.4 + grouping_score * 0.3 + adjacency_score * 0.3
        return round(min(100, max(0, final)), 1)

    def score_movement_flow(self, placements, furniture_pieces):
        """Score circulation quality (0-100).

        Considers:
        - Free area ratio
        - Door accessibility
        - Path connectivity
        """
        if not placements:
            return 100  # Empty room has perfect flow

        furniture_polys = []
        for piece, (x, y, rot) in zip(furniture_pieces, placements):
            poly = piece.get_polygon(x, y, rot)
            if poly.is_valid:
                furniture_polys.append(poly)

        if not furniture_polys:
            return 100

        furniture_union = unary_union(furniture_polys)
        free_space = self.room.polygon.difference(furniture_union)

        if free_space.is_empty:
            return 0

        # Free area ratio (target: 40-60% free)
        free_ratio = free_space.area / self.room.polygon.area
        if free_ratio >= 0.4:
            ratio_score = 100
        elif free_ratio >= 0.25:
            ratio_score = 50 + (free_ratio - 0.25) / 0.15 * 50
        else:
            ratio_score = free_ratio / 0.25 * 50

        # Door accessibility
        door_score = 100
        for door in self.room.doors:
            door_point = Point(door.position)
            dist_to_free = free_space.distance(door_point)
            if dist_to_free > 50:
                door_score -= 30
            elif dist_to_free > 20:
                door_score -= 10

        door_score = max(0, door_score)

        # Path width check — sample paths between doors and room center
        path_score = 100
        center = self.room.centroid
        for door in self.room.doors:
            path_line = LineString([door.position, center])
            intersections = path_line.intersection(furniture_union)
            if not intersections.is_empty:
                # Path is blocked — penalize
                if intersections.length > 0:
                    blocked_ratio = intersections.length / path_line.length
                    path_score -= blocked_ratio * 40

        path_score = max(0, path_score)

        final = ratio_score * 0.4 + door_score * 0.35 + path_score * 0.25
        return round(min(100, max(0, final)), 1)

    def score_layout(self, placements, furniture_pieces):
        """Compute full layout score across all axes.

        Returns:
            dict with per-axis scores, composite score, and grade
        """
        space = self.score_space_efficiency(placements, furniture_pieces)
        usability = self.score_usability(placements, furniture_pieces)

        if self.daylight:
            daylight_result = self.daylight.score_layout(placements, furniture_pieces)
            daylight = daylight_result["overall"]
        else:
            daylight = 50  # Neutral if no daylight analysis

        flow = self.score_movement_flow(placements, furniture_pieces)

        composite = (
            space * self.weights["space_efficiency"]
            + usability * self.weights["usability"]
            + daylight * self.weights["daylight_comfort"]
            + flow * self.weights["movement_flow"]
        )

        # Grade
        if composite >= 85:
            grade = "A+"
        elif composite >= 75:
            grade = "A"
        elif composite >= 65:
            grade = "B+"
        elif composite >= 55:
            grade = "B"
        elif composite >= 45:
            grade = "C"
        else:
            grade = "D"

        return {
            "composite": round(composite, 1),
            "grade": grade,
            "axes": {
                "space_efficiency": round(space, 1),
                "usability": round(usability, 1),
                "daylight_comfort": round(daylight, 1),
                "movement_flow": round(flow, 1),
            },
            "weights": self.weights,
        }
