"""
Architectural constraint engine using Neufert standards.
"""

import math
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
import numpy as np


class ConstraintChecker:
    """Checks layout constraints based on Neufert architectural standards."""

    # Neufert reference standards (cm)
    STANDARDS = {
        "door_clearance": 100,
        "primary_corridor": 120,
        "secondary_corridor": 90,
        "wheelchair_turning": 150,
        "workstation_spacing": 140,
        "desk_wall_gap": 5,
        "meeting_chair_clearance": 80,
        "min_passage": 75,
        "storage_access": 70,
        "chair_pullback": 60,
    }

    def __init__(self, room_geometry, config=None):
        self.room = room_geometry
        self.config = config or {}

        # Override standards from config
        for key in self.STANDARDS:
            config_key = key.upper()
            if config_key in (self.config.__dict__ if hasattr(self.config, '__dict__') else {}):
                self.STANDARDS[key] = getattr(self.config, config_key)

        # Pre-compute room features
        self.door_zones = room_geometry.get_door_clearance_zones(
            self.STANDARDS["door_clearance"]
        )
        self.door_exclusion = unary_union(self.door_zones) if self.door_zones else Polygon()

    def check_all(self, placements, furniture_pieces):
        """Check all constraints for a layout.

        Args:
            placements: List of (x, y, rotation) tuples
            furniture_pieces: List of FurniturePiece objects (same order)

        Returns:
            dict with constraint results and penalty score
        """
        results = {
            "valid": True,
            "total_penalty": 0,
            "violations": [],
            "collision_penalty": 0,
            "boundary_penalty": 0,
            "door_penalty": 0,
            "spacing_penalty": 0,
            "wall_bonus": 0,
        }

        polygons = []
        clearance_polygons = []

        for i, (piece, placement) in enumerate(zip(furniture_pieces, placements)):
            x, y, rot = placement
            poly = piece.get_polygon(x, y, rot)
            cpoly = piece.get_clearance_polygon(x, y, rot)
            polygons.append(poly)
            clearance_polygons.append(cpoly)

        # 1. Boundary check — all furniture must be inside room
        for i, poly in enumerate(polygons):
            if not self.room.polygon.contains(poly):
                # How much is outside?
                if poly.intersects(self.room.polygon):
                    outside = poly.difference(self.room.polygon)
                    penalty = (outside.area / poly.area) * 500
                else:
                    penalty = 1000  # Completely outside
                results["boundary_penalty"] += penalty
                results["violations"].append({
                    "type": "boundary",
                    "piece_index": i,
                    "severity": "critical",
                })

        # 2. Collision check — no furniture overlap
        for i in range(len(polygons)):
            for j in range(i + 1, len(polygons)):
                if polygons[i].intersects(polygons[j]):
                    overlap = polygons[i].intersection(polygons[j])
                    penalty = overlap.area * 0.5
                    results["collision_penalty"] += penalty
                    results["violations"].append({
                        "type": "collision",
                        "pieces": [i, j],
                        "severity": "critical",
                    })

        # 3. Door clearance — furniture must not block door zones
        if not self.door_exclusion.is_empty:
            for i, poly in enumerate(polygons):
                if poly.intersects(self.door_exclusion):
                    overlap = poly.intersection(self.door_exclusion)
                    penalty = overlap.area * 2.0
                    results["door_penalty"] += penalty
                    results["violations"].append({
                        "type": "door_clearance",
                        "piece_index": i,
                        "severity": "major",
                    })

        # 4. Workstation spacing — check minimum distance between desks
        desk_categories = {"work_desk", "shared_table"}
        desk_indices = [
            i for i, p in enumerate(furniture_pieces)
            if p.category in desk_categories
        ]
        min_spacing = self.STANDARDS["workstation_spacing"]

        for i in range(len(desk_indices)):
            for j in range(i + 1, len(desk_indices)):
                idx_i, idx_j = desk_indices[i], desk_indices[j]
                ci = polygons[idx_i].centroid
                cj = polygons[idx_j].centroid
                dist = ci.distance(cj)
                if dist < min_spacing and dist > 0:
                    penalty = (min_spacing - dist) * 0.3
                    results["spacing_penalty"] += penalty

        # 5. Wall adjacency bonus — reward wall-hugging for high wall_affinity pieces
        for i, (piece, placement) in enumerate(zip(furniture_pieces, placements)):
            if piece.wall_affinity > 0.5:
                x, y, _ = placement
                min_wall_dist = float("inf")
                for start, end in self.room.walls:
                    wall_line = LineString([start, end])
                    dist = wall_line.distance(Point(x, y))
                    min_wall_dist = min(min_wall_dist, dist)

                max_dim = max(piece.width, piece.depth) / 2
                if min_wall_dist <= max_dim + 20:
                    results["wall_bonus"] += piece.wall_affinity * 30
                elif piece.wall_affinity >= 0.8:
                    results["spacing_penalty"] += (min_wall_dist - max_dim) * 0.1

        # Tally
        results["total_penalty"] = (
            results["collision_penalty"]
            + results["boundary_penalty"]
            + results["door_penalty"]
            + results["spacing_penalty"]
            - results["wall_bonus"]
        )

        results["valid"] = (
            results["collision_penalty"] == 0
            and results["boundary_penalty"] == 0
            and results["door_penalty"] == 0
        )

        return results

    def get_circulation_paths(self, placements, furniture_pieces, min_width=90):
        """Analyze circulation paths through the layout.

        Returns the free space polygon and a connectivity score.
        """
        furniture_union = Polygon()
        for piece, (x, y, rot) in zip(furniture_pieces, placements):
            poly = piece.get_polygon(x, y, rot)
            if poly.is_valid:
                furniture_union = furniture_union.union(poly)

        free_space = self.room.polygon.difference(furniture_union)
        if free_space.is_empty:
            return {"free_area_ratio": 0, "connected": False}

        # Check if all doors are reachable from free space
        doors_reachable = 0
        for door in self.room.doors:
            door_point = Point(door.position)
            if free_space.distance(door_point) < min_width:
                doors_reachable += 1

        total_doors = max(len(self.room.doors), 1)

        return {
            "free_area": free_space.area,
            "free_area_ratio": free_space.area / self.room.polygon.area,
            "doors_reachable": doors_reachable,
            "door_accessibility": doors_reachable / total_doors,
            "connected": doors_reachable == len(self.room.doors),
        }
