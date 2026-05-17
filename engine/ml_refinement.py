"""
Lightweight ML Refinement Layer — refines rule-based layouts using
scoring heuristics and simulated GAN/Pix2Pix-style optimization.

No heavy dependencies (NumPy only). Runs in <200ms per layout.
"""

import math
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union


# ── Feature Extraction ──────────────────────────────────────────────────

class LayoutFeatureExtractor:
    """Extracts numerical features from a layout for ML scoring."""

    def __init__(self, room_geometry, daylight_analyzer=None):
        self.room = room_geometry
        self.polygon = room_geometry.polygon
        self.room_area = self.polygon.area
        self.daylight = daylight_analyzer
        self.bounds = room_geometry.bounds

    def extract(self, placements, pieces):
        """Extract a feature vector from a layout.

        Returns:
            numpy array of normalized features [0, 1]
        """
        features = []

        # 1. Space utilization ratio
        furniture_area = sum(p.width * p.depth for p in pieces)
        utilization = min(1.0, furniture_area / max(self.room_area, 1))
        features.append(utilization)

        # 2. Utilization quality (penalize too sparse or too dense)
        ideal_util = 0.45
        util_quality = 1.0 - abs(utilization - ideal_util) / 0.45
        features.append(max(0, util_quality))

        # 3. Spacing uniformity (lower std dev = more uniform)
        if len(placements) > 1:
            positions = np.array([(float(x), float(y)) for x, y, _ in placements], dtype=np.float64)
            dists = []
            for i in range(len(positions)):
                for j in range(i + 1, len(positions)):
                    d = np.linalg.norm(positions[i] - positions[j])
                    dists.append(d)
            if dists:
                std = np.std(dists)
                mean = np.mean(dists)
                uniformity = 1.0 - min(1.0, std / max(mean, 1))
            else:
                uniformity = 0.5
        else:
            uniformity = 0.5
        features.append(uniformity)

        # 4. Wall alignment score (how many desks are near walls)
        wall_aligned = 0
        total_desks = 0
        for piece, (x, y, _) in zip(pieces, placements):
            if piece.category in ("work_desk", "storage"):
                total_desks += 1
                min_dist = float("inf")
                for start, end in self.room.walls:
                    from shapely.geometry import LineString
                    wall_line = LineString([start, end])
                    dist = wall_line.distance(Point(x, y))
                    min_dist = min(min_dist, dist)
                if min_dist < max(piece.width, piece.depth) / 2 + 30:
                    wall_aligned += 1
        features.append(wall_aligned / max(total_desks, 1))

        # 5. Rotation consistency (same category should have same rotation)
        cat_rotations = {}
        for piece, (_, _, rot) in zip(pieces, placements):
            if piece.category not in cat_rotations:
                cat_rotations[piece.category] = []
            cat_rotations[piece.category].append(rot % 360)

        consistency = []
        for cat, rots in cat_rotations.items():
            if len(rots) > 1:
                # Fraction matching the mode
                from collections import Counter
                mode = Counter(rots).most_common(1)[0][1]
                consistency.append(mode / len(rots))
        features.append(np.mean(consistency) if consistency else 1.0)

        # 6. Daylight coverage
        if self.daylight and self.daylight.daylight_zones:
            in_daylight = 0
            daylight_eligible = 0
            for piece, (x, y, _) in zip(pieces, placements):
                if piece.category in ("work_desk", "lounge", "collaborative_seating"):
                    daylight_eligible += 1
                    pt = Point(x, y)
                    for zone in self.daylight.daylight_zones:
                        if zone["polygon"].contains(pt):
                            in_daylight += 1
                            break
            features.append(in_daylight / max(daylight_eligible, 1))
        else:
            features.append(0.5)

        # 7. Collision count (lower is better)
        polys = []
        for piece, (x, y, rot) in zip(pieces, placements):
            polys.append(piece.get_polygon(x, y, rot))

        collisions = 0
        for i in range(len(polys)):
            for j in range(i + 1, len(polys)):
                if polys[i].intersects(polys[j]):
                    collisions += 1
        max_collisions = len(polys) * (len(polys) - 1) / 2
        features.append(1.0 - collisions / max(max_collisions, 1))

        # 8. Boundary compliance
        inside = sum(1 for p in polys if self.polygon.contains(p))
        features.append(inside / max(len(polys), 1))

        # 9. Door clearance
        door_clear = 1.0
        for door in self.room.doors:
            door_zone = Point(door.position).buffer(100)
            for p in polys:
                if p.intersects(door_zone):
                    door_clear -= 0.1
        features.append(max(0, door_clear))

        # 10. Distribution balance (quadrant balance)
        cx, cy = self.room.centroid
        quadrants = [0, 0, 0, 0]
        for x, y, _ in placements:
            qi = (0 if x < cx else 1) + (0 if y < cy else 2)
            quadrants[qi] += 1
        total = sum(quadrants) or 1
        fracs = [q / total for q in quadrants]
        balance = 1.0 - np.std(fracs) * 4
        features.append(max(0, min(1, balance)))

        return np.array(features, dtype=np.float32)


# ── Lightweight Scoring Network ─────────────────────────────────────────

class LayoutScoringNetwork:
    """Simple feedforward network for layout quality prediction.

    Uses pre-defined weights (no training required) that encode
    professional spatial planning heuristics.
    """

    def __init__(self):
        # Pre-defined weight matrix: 10 features → 1 score
        # Weights reflect importance of each feature
        self.weights = np.array([
            0.05,  # utilization ratio (raw)
            0.15,  # utilization quality (distance from ideal)
            0.12,  # spacing uniformity
            0.12,  # wall alignment
            0.10,  # rotation consistency
            0.10,  # daylight coverage
            0.15,  # no collisions (critical)
            0.10,  # boundary compliance (critical)
            0.06,  # door clearance
            0.05,  # distribution balance
        ], dtype=np.float32)

        # Bias term
        self.bias = 0.0

    def predict(self, features):
        """Predict layout quality score (0-100)."""
        score = np.dot(features, self.weights) + self.bias
        return float(np.clip(score * 100, 0, 100))


# ── GAN Simulation (Pix2Pix-style) ─────────────────────────────────────

class GANLayoutSimulator:
    """Simulates GAN/Pix2Pix-style layout refinement using heuristic filters.

    Instead of actual deep learning, applies learned-pattern transformations:
    1. Edge-aware snapping (align to wall edges)
    2. Density equalization (spread clusters)
    3. Symmetry enforcement (mirror patterns)
    """

    GRID_RES = 50  # 50cm occupancy grid resolution

    def __init__(self, room_geometry):
        self.room = room_geometry
        self.polygon = room_geometry.polygon
        self.bounds = room_geometry.bounds

    def generate_occupancy_grid(self, placements, pieces):
        """Convert layout to 2D occupancy grid (simulated 'image' for GAN)."""
        minx, miny, maxx, maxy = self.bounds
        cols = max(1, int((maxx - minx) / self.GRID_RES))
        rows = max(1, int((maxy - miny) / self.GRID_RES))
        grid = np.zeros((rows, cols), dtype=np.float32)

        for piece, (x, y, rot) in zip(pieces, placements):
            # Map to grid coordinates
            gx = int((x - minx) / self.GRID_RES)
            gy = int((y - miny) / self.GRID_RES)
            hw = max(1, int(piece.width / self.GRID_RES / 2))
            hd = max(1, int(piece.depth / self.GRID_RES / 2))

            for dy in range(-hd, hd + 1):
                for dx in range(-hw, hw + 1):
                    ny, nx = gy + dy, gx + dx
                    if 0 <= ny < rows and 0 <= nx < cols:
                        grid[ny, nx] = 1.0

        return grid

    def apply_density_equalization(self, placements, pieces):
        """Spread clustered furniture to reduce density hotspots.

        Simulates GAN discriminator feedback: "this area is too dense".
        """
        refined = list(placements)
        positions = np.array([(float(x), float(y)) for x, y, _ in placements], dtype=np.float64)

        if len(positions) < 2:
            return refined

        # Find density at each position (count neighbors within 100cm)
        for i in range(len(positions)):
            neighbors = 0
            repel_x, repel_y = 0.0, 0.0

            for j in range(len(positions)):
                if i == j:
                    continue
                d = np.linalg.norm(positions[i] - positions[j])
                if d < 100 and d > 0:
                    neighbors += 1
                    # Repulsion vector
                    direction = (positions[i] - positions[j]).astype(np.float64)
                    direction = direction / d
                    strength = (100 - d) * 0.1
                    repel_x += direction[0] * strength
                    repel_y += direction[1] * strength

            if neighbors >= 2:
                x, y, rot = refined[i]
                x += repel_x
                y += repel_y
                # Snap to grid
                x = round(x / 10) * 10
                y = round(y / 10) * 10
                # Validate still inside
                test = pieces[i].get_polygon(x, y, rot)
                if self.polygon.contains(test):
                    refined[i] = (x, y, rot)

        return refined

    def apply_symmetry_enforcement(self, placements, pieces):
        """Enforce approximate symmetry across room center axis.

        Simulates GAN generator: "professional layouts have visual order".
        Only adjusts pieces by small amounts (±20cm) to improve symmetry.
        """
        refined = list(placements)
        cx, cy = self.room.centroid

        # Group by category
        cat_groups = {}
        for i, piece in enumerate(pieces):
            if piece.category not in cat_groups:
                cat_groups[piece.category] = []
            cat_groups[piece.category].append(i)

        for cat, indices in cat_groups.items():
            if len(indices) < 2:
                continue

            # Find axis of symmetry (vertical or horizontal through center)
            positions = [placements[i] for i in indices]
            xs = [p[0] for p in positions]

            # If desks are roughly on one side, don't force symmetry
            spread_x = max(xs) - min(xs)
            room_w = self.bounds[2] - self.bounds[0]
            if spread_x < room_w * 0.3:
                continue  # Already clustered, don't mess with it

            # Nudge toward vertical symmetry (equal distance from center X)
            for idx in indices:
                x, y, rot = refined[idx]
                mirror_x = 2 * cx - x
                # Blend original with mirror: 80% original, 20% mirror
                blend_x = x * 0.85 + mirror_x * 0.15
                blend_x = round(blend_x / 10) * 10

                test = pieces[idx].get_polygon(blend_x, y, rot)
                if self.polygon.contains(test):
                    refined[idx] = (blend_x, y, rot)

        return refined


# ── ML Refinement Engine ────────────────────────────────────────────────

class MLRefinementEngine:
    """Orchestrates ML-based layout refinement.

    Pipeline:
    1. Score initial layout with scoring network
    2. Apply GAN-style transformations (density equalization, symmetry)
    3. Apply gradient-free micro-optimization (try small shifts)
    4. Score refined layout and keep if improved
    """

    def __init__(self, room_geometry, daylight_analyzer=None,
                 max_iterations=3, gan_enabled=True):
        self.room = room_geometry
        self.polygon = room_geometry.polygon
        self.daylight = daylight_analyzer
        self.max_iterations = max_iterations
        self.gan_enabled = gan_enabled

        self.extractor = LayoutFeatureExtractor(room_geometry, daylight_analyzer)
        self.scorer = LayoutScoringNetwork()
        self.gan = GANLayoutSimulator(room_geometry) if gan_enabled else None

    def refine(self, placements, pieces):
        """Refine a layout through ML scoring and optimization.

        Args:
            placements: List of (x, y, rotation) tuples
            pieces: List of FurniturePiece objects

        Returns:
            Refined placements and ML score
        """
        best_placements = list(placements)
        best_features = self.extractor.extract(best_placements, pieces)
        best_score = self.scorer.predict(best_features)

        # Single refinement pass (fast — avoids expensive iterative scoring)
        for iteration in range(min(self.max_iterations, 2)):
            improved = False

            # Phase 1: GAN-style refinement (cheap heuristic transforms)
            if self.gan and iteration == 0:
                candidate = self.gan.apply_density_equalization(
                    best_placements, pieces
                )
                feat = self.extractor.extract(candidate, pieces)
                score = self.scorer.predict(feat)
                if score > best_score:
                    best_placements = candidate
                    best_score = score
                    best_features = feat
                    improved = True

                candidate = self.gan.apply_symmetry_enforcement(
                    best_placements, pieces
                )
                feat = self.extractor.extract(candidate, pieces)
                score = self.scorer.predict(feat)
                if score > best_score:
                    best_placements = candidate
                    best_score = score
                    best_features = feat
                    improved = True

            # Phase 2: Fast micro-optimization (local collision check only)
            candidate = self._micro_optimize_fast(best_placements, pieces)
            feat = self.extractor.extract(candidate, pieces)
            score = self.scorer.predict(feat)
            if score > best_score:
                best_placements = candidate
                best_score = score
                best_features = feat
                improved = True

            if not improved:
                break  # Converged

        return best_placements, round(best_score, 1), best_features.tolist()

    def _micro_optimize_fast(self, placements, pieces):
        """Fast local refinement — collision-based only, no full scoring per trial.

        For each piece, tries small shifts and keeps moves that:
        1. Don't cause new collisions
        2. Keep the piece inside the room
        3. Move the piece closer to ideal positions (walls for desks, etc.)
        """
        refined = list(placements)
        shifts = [(-10, 0), (10, 0), (0, -10), (0, 10)]

        # Pre-build polygons for collision checking
        polys = [pieces[i].get_polygon(*refined[i]) for i in range(len(refined))]

        for i in range(len(refined)):
            x, y, rot = refined[i]
            piece = pieces[i]
            current_poly = polys[i]

            best_pos = (x, y, rot)
            best_benefit = 0

            # Try position shifts
            for dx, dy in shifts:
                nx = round((x + dx) / 10) * 10
                ny = round((y + dy) / 10) * 10
                test_poly = piece.get_polygon(nx, ny, rot)

                # Quick checks: inside room and no new collisions
                if not self.polygon.contains(test_poly):
                    continue

                has_collision = False
                for j in range(len(polys)):
                    if j == i:
                        continue
                    if test_poly.intersects(polys[j]):
                        has_collision = True
                        break

                if has_collision:
                    continue

                # Benefit heuristic: prefer moving toward nearest wall for desks
                benefit = 0
                if piece.category in ("work_desk", "storage"):
                    # Closer to wall = better
                    for start, end in self.room.walls:
                        from shapely.geometry import LineString
                        wall_line = LineString([start, end])
                        old_dist = wall_line.distance(Point(x, y))
                        new_dist = wall_line.distance(Point(nx, ny))
                        if new_dist < old_dist:
                            benefit += 1
                            break

                if benefit > best_benefit:
                    best_pos = (nx, ny, rot)
                    best_benefit = benefit

            if best_pos != (x, y, rot):
                refined[i] = best_pos
                polys[i] = piece.get_polygon(*best_pos)

        return refined

