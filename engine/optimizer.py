"""
Layout optimizer — hybrid rule-based + ML refinement (primary), with GA fallback.

The hybrid approach runs in <500ms vs the GA's 10-30s.
"""

import math
import random
import copy
import time
import numpy as np
from shapely.geometry import Polygon, Point

from .geometry import RoomGeometry
from .furniture import FurniturePiece
from .constraints import ConstraintChecker
from .daylight import DaylightAnalyzer
from .scoring import LayoutScorer
from .layout_rules import LayoutRulesEngine
from .grid_layout_engine import GridLayoutEngine
from .ml_refinement import MLRefinementEngine


class Individual:
    """Represents a single layout solution (chromosome) — used by GA fallback."""

    __slots__ = ['genes', 'fitness', 'scores']

    def __init__(self, genes):
        self.genes = genes  # List of (x, y, rotation) per furniture piece
        self.fitness = -float('inf')
        self.scores = None


class HybridLayoutOptimizer:
    """Primary optimizer: Grid Engine → ML Refinement → Scoring.

    Produces professional-quality layouts in <500ms.
    """

    def __init__(self, room_geometry, furniture_pieces, daylight_analyzer=None,
                 num_layouts=4, use_case="hybrid_flex",
                 ml_iterations=3, gan_enabled=True):

        self.room = room_geometry
        self.pieces = furniture_pieces
        self.daylight = daylight_analyzer
        self.scorer = LayoutScorer(room_geometry, daylight_analyzer)
        self.use_case = use_case
        self.num_layouts = num_layouts

        # Initialize engines
        self.grid_engine = GridLayoutEngine(room_geometry, daylight_analyzer)
        self.ml_engine = MLRefinementEngine(
            room_geometry, daylight_analyzer,
            max_iterations=ml_iterations,
            gan_enabled=gan_enabled,
        )

    def optimize(self):
        """Run hybrid optimization pipeline.

        Returns:
            dict with layouts, timing, and metadata
        """
        start_time = time.time()

        # Phase 1: Grid-based deterministic layouts (~50ms)
        t1 = time.time()
        variants = self.grid_engine.generate_variants(
            self.pieces, self.use_case, self.num_layouts
        )
        grid_time = time.time() - t1

        # Phase 2: ML refinement on each variant (~100-200ms)
        t2 = time.time()
        refined_layouts = []
        for variant in variants:
            refined_placements, ml_score, ml_features = self.ml_engine.refine(
                variant, self.pieces
            )
            refined_layouts.append({
                "placements": refined_placements,
                "ml_score": ml_score,
                "ml_features": ml_features,
            })
        ml_time = time.time() - t2

        # Phase 3: Score all layouts with full scorer (~50ms)
        t3 = time.time()
        scored_layouts = []
        for layout_data in refined_layouts:
            scores = self.scorer.score_layout(
                layout_data["placements"], self.pieces
            )
            scored_layouts.append({
                "placements": layout_data["placements"],
                "scores": scores,
                "ml_score": layout_data["ml_score"],
                "ml_features": layout_data["ml_features"],
                "fitness": scores["composite"],
            })
        score_time = time.time() - t3

        # Sort by composite score
        scored_layouts.sort(key=lambda l: l["fitness"], reverse=True)

        # Select diverse layouts
        selected = self._select_diverse(scored_layouts, self.num_layouts)

        elapsed = time.time() - start_time

        # Build results
        results = []
        for i, layout in enumerate(selected):
            results.append({
                "layout_id": i + 1,
                "placements": [
                    {
                        "piece_id": piece.id,
                        "x": round(g[0], 1),
                        "y": round(g[1], 1),
                        "rotation": g[2],
                        "width": piece.width,
                        "depth": piece.depth,
                        "category": piece.category,
                        "name": piece.name,
                        "color": piece.color,
                    }
                    for piece, g in zip(self.pieces, layout["placements"])
                ],
                "scores": layout["scores"],
                "fitness": round(layout["fitness"], 2),
                "ml_score": layout["ml_score"],
            })

        return {
            "layouts": results,
            "engine": "hybrid",
            "time_seconds": round(elapsed, 3),
            "timing": {
                "grid_engine_ms": round(grid_time * 1000, 1),
                "ml_refinement_ms": round(ml_time * 1000, 1),
                "scoring_ms": round(score_time * 1000, 1),
                "total_ms": round(elapsed * 1000, 1),
            },
            "population_size": self.num_layouts,
            "generations_run": 0,
        }

    def _select_diverse(self, layouts, n):
        """Select n diverse layouts from scored candidates."""
        if len(layouts) <= n:
            return layouts

        selected = [layouts[0]]

        for candidate in layouts[1:]:
            if len(selected) >= n:
                break
            is_diverse = True
            for existing in selected:
                similarity = self._compute_similarity(
                    candidate["placements"], existing["placements"]
                )
                if similarity > 0.9:
                    is_diverse = False
                    break
            if is_diverse:
                selected.append(candidate)

        # Fill remaining
        for candidate in layouts:
            if len(selected) >= n:
                break
            if candidate not in selected:
                selected.append(candidate)

        return selected[:n]

    def _compute_similarity(self, placements1, placements2):
        """Measure layout similarity (0=different, 1=identical)."""
        if len(placements1) != len(placements2):
            return 0

        total_dist = 0
        max_dist = math.hypot(
            self.room.bounds[2] - self.room.bounds[0],
            self.room.bounds[3] - self.room.bounds[1],
        ) or 1

        for p1, p2 in zip(placements1, placements2):
            pos_dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1]) / max_dist
            rot_diff = 1 if p1[2] != p2[2] else 0
            total_dist += pos_dist + rot_diff * 0.3

        avg_dist = total_dist / len(placements1) if placements1 else 0
        return max(0, 1 - avg_dist)


class GeneticLayoutOptimizer:
    """Fallback GA optimizer — used only when hybrid is disabled.

    Reduced parameters for faster execution (20 pop × 30 gen).
    """

    def __init__(self, room_geometry, furniture_pieces, daylight_analyzer=None,
                 population_size=20, generations=30, mutation_rate=0.15,
                 crossover_rate=0.7, elite_count=3, tournament_size=3,
                 early_stop=8, num_layouts=4, use_case="hybrid_flex"):

        self.room = room_geometry
        self.pieces = furniture_pieces
        self.daylight = daylight_analyzer
        self.constraint_checker = ConstraintChecker(room_geometry)
        self.scorer = LayoutScorer(room_geometry, daylight_analyzer)
        self.layout_rules = LayoutRulesEngine(room_geometry)
        self.use_case = use_case

        self.pop_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_count = elite_count
        self.tournament_size = tournament_size
        self.early_stop = early_stop
        self.num_layouts = num_layouts

        # Room bounds for gene initialization
        bounds = room_geometry.bounds
        self.min_x = bounds[0]
        self.min_y = bounds[1]
        self.max_x = bounds[2]
        self.max_y = bounds[3]

        # Pre-compute room centroid
        self.room_cx, self.room_cy = room_geometry.centroid

    def _random_position_inside(self):
        """Generate a random position guaranteed inside the room."""
        for _ in range(100):
            x = random.uniform(self.min_x + 50, self.max_x - 50)
            y = random.uniform(self.min_y + 50, self.max_y - 50)
            if self.room.point_in_room(x, y):
                return x, y
        return self.room_cx, self.room_cy

    def _random_rotation(self):
        """Random rotation in 90-degree increments."""
        return random.choice([0, 90, 180, 270])

    def _create_individual(self, strategy="smart"):
        """Create an individual with a specific strategy."""
        genes = []

        if strategy == "smart":
            # Use layout rules engine for intelligent placement
            placements = self.layout_rules.generate_smart_placement(
                self.pieces, use_case=self.use_case
            )
            genes = list(placements)

        elif strategy == "smart_variant":
            # Smart placement with random perturbation
            placements = self.layout_rules.generate_smart_placement(
                self.pieces, use_case=self.use_case
            )
            genes = []
            for x, y, rot in placements:
                x += random.gauss(0, 30)
                y += random.gauss(0, 30)
                if random.random() < 0.2:
                    rot = (rot + 90) % 360
                # Ensure still inside room
                x, y = self.layout_rules._clamp_to_room(
                    x, y, self.pieces[len(genes)], rot
                )
                genes.append((x, y, rot))

        elif strategy == "wall_hugging":
            # Place furniture near walls
            walls = self.room.walls
            for piece in self.pieces:
                wall = random.choice(walls)
                t = random.uniform(0.2, 0.8)
                x = wall[0][0] + (wall[1][0] - wall[0][0]) * t
                y = wall[0][1] + (wall[1][1] - wall[0][1]) * t
                wx = wall[1][0] - wall[0][0]
                wy = wall[1][1] - wall[0][1]
                wlen = math.hypot(wx, wy) or 1
                nx, ny = -wy / wlen, wx / wlen
                # Check inward normal
                test_x = x + nx * 10
                test_y = y + ny * 10
                if not self.room.point_in_room(test_x, test_y):
                    nx, ny = -nx, -ny
                offset = max(piece.width, piece.depth) / 2 + 10
                x += nx * offset
                y += ny * offset
                rot = self._random_rotation()
                x, y = self.layout_rules._clamp_to_room(x, y, piece, rot)
                genes.append((x, y, rot))

        elif strategy == "grid":
            n = len(self.pieces)
            cols = max(1, int(math.sqrt(n)))
            rows = math.ceil(n / cols)
            # Use room interior bounds with margin
            margin = 80
            dx = (self.max_x - self.min_x - margin * 2) / max(cols, 1)
            dy = (self.max_y - self.min_y - margin * 2) / max(rows, 1)
            for i, piece in enumerate(self.pieces):
                col = i % cols
                row = i // cols
                x = self.min_x + margin + dx * (col + 0.5) + random.gauss(0, 15)
                y = self.min_y + margin + dy * (row + 0.5) + random.gauss(0, 15)
                rot = self._random_rotation()
                x, y = self.layout_rules._clamp_to_room(x, y, piece, rot)
                genes.append((x, y, rot))

        else:  # random
            for piece in self.pieces:
                x, y = self._random_position_inside()
                rot = self._random_rotation()
                x, y = self.layout_rules._clamp_to_room(x, y, piece, rot)
                genes.append((x, y, rot))

        return Individual(genes)

    def _repair_individual(self, individual):
        """Repair an individual — enforce all furniture inside room bounds."""
        repaired = list(individual.genes)
        for i, (x, y, rot) in enumerate(repaired):
            piece = self.pieces[i]
            poly = piece.get_polygon(x, y, rot)
            if not self.room.polygon.contains(poly):
                x, y = self.layout_rules._clamp_to_room(x, y, piece, rot)
                repaired[i] = (x, y, rot)
        individual.genes = repaired
        return individual

    def _evaluate(self, individual):
        """Evaluate fitness of an individual."""
        placements = individual.genes

        # Constraint check
        constraint_result = self.constraint_checker.check_all(placements, self.pieces)
        penalty = constraint_result["total_penalty"]

        # Layout scoring
        scores = self.scorer.score_layout(placements, self.pieces)

        # Fitness = composite score - penalties
        # Heavier penalty for boundary violations to strongly discourage them
        boundary_pen = constraint_result["boundary_penalty"] * 2.0
        collision_pen = constraint_result["collision_penalty"] * 0.5
        door_pen = constraint_result["door_penalty"] * 1.0

        fitness = scores["composite"] - (boundary_pen + collision_pen + door_pen) * 0.1

        individual.fitness = fitness
        individual.scores = scores
        return fitness

    def _tournament_select(self, population):
        """Tournament selection."""
        candidates = random.sample(population, min(self.tournament_size, len(population)))
        return max(candidates, key=lambda ind: ind.fitness)

    def _crossover(self, parent1, parent2):
        """Two-point crossover on furniture genes."""
        if random.random() > self.crossover_rate:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        n = len(parent1.genes)
        if n < 2:
            return copy.deepcopy(parent1), copy.deepcopy(parent2)

        pt1 = random.randint(0, n - 1)
        pt2 = random.randint(pt1, n - 1)

        child1_genes = list(parent1.genes[:pt1]) + list(parent2.genes[pt1:pt2]) + list(parent1.genes[pt2:])
        child2_genes = list(parent2.genes[:pt1]) + list(parent1.genes[pt1:pt2]) + list(parent2.genes[pt2:])

        return Individual(child1_genes), Individual(child2_genes)

    def _mutate(self, individual):
        """Mutate an individual's genes with boundary awareness."""
        mutated_genes = list(individual.genes)

        for i in range(len(mutated_genes)):
            if random.random() < self.mutation_rate:
                x, y, rot = mutated_genes[i]
                piece = self.pieces[i]
                mutation_type = random.random()

                if mutation_type < 0.4:
                    # Small position perturbation
                    sigma = (self.max_x - self.min_x) * 0.05
                    x += random.gauss(0, sigma)
                    y += random.gauss(0, sigma)
                elif mutation_type < 0.6:
                    # Rotation flip
                    rot = (rot + 90) % 360
                elif mutation_type < 0.8:
                    # Wall snap — move to nearest wall
                    min_dist = float('inf')
                    best_x, best_y = x, y
                    for start, end in self.room.walls:
                        dx = end[0] - start[0]
                        dy = end[1] - start[1]
                        l = math.hypot(dx, dy)
                        if l == 0:
                            continue
                        t = max(0.1, min(0.9, ((x - start[0]) * dx + (y - start[1]) * dy) / (l * l)))
                        px = start[0] + t * dx
                        py = start[1] + t * dy
                        d = math.hypot(x - px, y - py)
                        if d < min_dist:
                            min_dist = d
                            # Offset inward
                            nx, ny = -dy / l, dx / l
                            test_x = px + nx * 10
                            test_y = py + ny * 10
                            if not self.room.point_in_room(test_x, test_y):
                                nx, ny = -nx, -ny
                            offset = max(piece.width, piece.depth) / 2 + 10
                            best_x = px + nx * offset
                            best_y = py + ny * offset
                    x, y = best_x, best_y
                else:
                    # Random reposition inside room
                    x, y = self._random_position_inside()
                    rot = self._random_rotation()

                # Snap to grid (10cm) and clamp
                x = round(x / 10) * 10
                y = round(y / 10) * 10
                x, y = self.layout_rules._clamp_to_room(x, y, piece, rot)
                mutated_genes[i] = (x, y, rot)

        individual.genes = mutated_genes
        return individual

    def _get_diverse_layouts(self, population, n=4):
        """Select n diverse, high-quality layouts from the population."""
        sorted_pop = sorted(population, key=lambda ind: ind.fitness, reverse=True)

        selected = [sorted_pop[0]]

        for candidate in sorted_pop[1:]:
            if len(selected) >= n:
                break

            is_diverse = True
            for existing in selected:
                similarity = self._layout_similarity(candidate, existing)
                if similarity > 0.85:
                    is_diverse = False
                    break

            if is_diverse:
                selected.append(candidate)

        while len(selected) < n and len(sorted_pop) > len(selected):
            for candidate in sorted_pop:
                if candidate not in selected:
                    selected.append(candidate)
                    break

        return selected[:n]

    def _layout_similarity(self, ind1, ind2):
        """Measure similarity between two layouts (0 = different, 1 = identical)."""
        if len(ind1.genes) != len(ind2.genes):
            return 0

        total_dist = 0
        max_dist = math.hypot(self.max_x - self.min_x, self.max_y - self.min_y)

        for g1, g2 in zip(ind1.genes, ind2.genes):
            pos_dist = math.hypot(g1[0] - g2[0], g1[1] - g2[1]) / (max_dist or 1)
            rot_diff = 1 if g1[2] != g2[2] else 0
            total_dist += pos_dist + rot_diff * 0.3

        avg_dist = total_dist / len(ind1.genes) if ind1.genes else 0
        return max(0, 1 - avg_dist)

    def optimize(self, time_limit=5):
        """Run the genetic algorithm (fallback mode).

        Args:
            time_limit: Maximum time in seconds (default reduced to 5s)

        Returns:
            List of top N layout results
        """
        start_time = time.time()
        random.seed()

        # Initialize population with mixed strategies (reduced pop size)
        population = []
        strategies = (
            ["smart"] * max(1, self.pop_size // 3)
            + ["smart_variant"] * max(1, self.pop_size // 3)
            + ["wall_hugging"] * max(1, self.pop_size // 6)
            + ["grid"] * max(1, self.pop_size // 12)
            + ["random"] * max(1, self.pop_size // 12)
        )

        for strategy in strategies[:self.pop_size]:
            ind = self._create_individual(strategy)
            self._repair_individual(ind)  # Hard boundary enforcement
            population.append(ind)

        # Fill remaining if needed
        while len(population) < self.pop_size:
            ind = self._create_individual("smart_variant")
            self._repair_individual(ind)
            population.append(ind)

        # Evaluate initial population
        for ind in population:
            self._evaluate(ind)

        best_fitness = max(ind.fitness for ind in population)
        stagnation = 0
        gen = 0

        for gen in range(self.generations):
            # Time check
            if time.time() - start_time > time_limit * 0.9:
                break

            # Early stopping
            if stagnation >= self.early_stop:
                break

            # Sort by fitness
            population.sort(key=lambda ind: ind.fitness, reverse=True)

            # Elitism
            new_population = [copy.deepcopy(ind) for ind in population[:self.elite_count]]

            # Generate offspring
            while len(new_population) < self.pop_size:
                parent1 = self._tournament_select(population)
                parent2 = self._tournament_select(population)

                child1, child2 = self._crossover(parent1, parent2)
                self._mutate(child1)
                self._mutate(child2)

                # Hard boundary enforcement on children
                self._repair_individual(child1)
                self._repair_individual(child2)

                self._evaluate(child1)
                self._evaluate(child2)

                new_population.append(child1)
                if len(new_population) < self.pop_size:
                    new_population.append(child2)

            population = new_population

            # Track improvement
            current_best = max(ind.fitness for ind in population)
            if current_best > best_fitness + 0.1:
                best_fitness = current_best
                stagnation = 0
            else:
                stagnation += 1

        # Select diverse top layouts
        top_layouts = self._get_diverse_layouts(population, self.num_layouts)

        elapsed = time.time() - start_time

        results = []
        for i, layout in enumerate(top_layouts):
            self._evaluate(layout)

            results.append({
                "layout_id": i + 1,
                "placements": [
                    {
                        "piece_id": piece.id,
                        "x": round(g[0], 1),
                        "y": round(g[1], 1),
                        "rotation": g[2],
                        "width": piece.width,
                        "depth": piece.depth,
                        "category": piece.category,
                        "name": piece.name,
                        "color": piece.color,
                    }
                    for piece, g in zip(self.pieces, layout.genes)
                ],
                "scores": layout.scores,
                "fitness": round(layout.fitness, 2),
            })

        return {
            "layouts": results,
            "engine": "genetic_algorithm",
            "generations_run": gen + 1,
            "time_seconds": round(elapsed, 2),
            "population_size": self.pop_size,
        }
