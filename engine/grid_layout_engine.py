"""
Grid Layout Engine — deterministic, rule-based layout generation.

Produces clean, aligned, professional coworking layouts in <100ms by using:
- Grid-snapped placement (10cm grid)
- Wall-hugging desks with uniform rotation
- Daylight-aware wall priority
- Ergonomic circulation corridors
- Chair-desk pairing
- Zone-based meeting/lounge placement
"""

import math
import copy
import time
from shapely.geometry import Polygon, Point, LineString
from shapely.ops import unary_union


# ── Architectural Standards (cm) ────────────────────────────────────────
GRID_SNAP = 10
DESK_WALL_GAP = 5
DOOR_CLEARANCE_RADIUS = 100
PRIMARY_CORRIDOR = 120
SECONDARY_CORRIDOR = 90
WORKSTATION_SPACING = 140
CHAIR_PULLBACK = 65          # Chair center behind desk front edge
MIN_PASSAGE = 75


class WallSegment:
    """Pre-computed wall segment data for fast placement."""

    __slots__ = [
        "index", "start", "end", "length", "angle_deg",
        "nx", "ny", "ux", "uy", "has_door", "has_window",
        "window_count", "daylight_score", "usable_ranges",
    ]

    def __init__(self, index, start, end, room_polygon, doors, windows):
        self.index = index
        self.start = start
        self.end = end

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        self.length = math.hypot(dx, dy)

        if self.length > 0:
            self.ux = dx / self.length
            self.uy = dy / self.length
            self.nx = -self.uy
            self.ny = self.ux
        else:
            self.ux = self.uy = self.nx = self.ny = 0

        # Check inward normal
        mid_x = (start[0] + end[0]) / 2 + self.nx * 10
        mid_y = (start[1] + end[1]) / 2 + self.ny * 10
        if not room_polygon.contains(Point(mid_x, mid_y)):
            self.nx, self.ny = -self.nx, -self.ny

        self.angle_deg = round(math.degrees(math.atan2(dy, dx)))

        # Door / window flags
        self.has_door = any(d.wall_index == index for d in doors)
        self.has_window = any(w.wall_index == index for w in windows)
        self.window_count = sum(1 for w in windows if w.wall_index == index)

        # Daylight score: more windows + bigger windows = higher score
        self.daylight_score = sum(
            w.width for w in windows if w.wall_index == index
        ) / max(self.length, 1)

        # Usable linear ranges along wall (excluding door clearance zones)
        self.usable_ranges = self._compute_usable_ranges(doors)

    def _compute_usable_ranges(self, doors):
        """Get usable t-ranges [0..1] along wall, excluding door zones."""
        blocked = []
        for door in doors:
            if door.wall_index != self.index:
                continue
            dx = door.position[0] - self.start[0]
            dy = door.position[1] - self.start[1]
            t_center = (dx * self.ux + dy * self.uy) / max(self.length, 1)
            half_clear = (door.width / 2 + DOOR_CLEARANCE_RADIUS) / max(self.length, 1)
            blocked.append((t_center - half_clear, t_center + half_clear))

        # Sort and merge blocked intervals
        blocked.sort()
        merged = []
        for lo, hi in blocked:
            if merged and lo <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))

        # Invert to get usable ranges (with margin from wall ends)
        margin = 0.05
        usable = []
        prev = margin
        for lo, hi in merged:
            if lo > prev:
                usable.append((prev, lo))
            prev = max(prev, hi)
        if prev < 1 - margin:
            usable.append((prev, 1 - margin))

        return usable if usable else [(margin, 1 - margin)]

    def desk_rotation(self):
        """Determine the 90°-snapped rotation for desks on this wall.
        Desk back faces wall, front faces room interior."""
        # Normal angle + 180° so desk front faces inward
        raw = math.degrees(math.atan2(self.ny, self.nx))
        return round(raw / 90) * 90 % 360


class GridLayoutEngine:
    """Deterministic grid-based layout engine for professional coworking spaces."""

    def __init__(self, room_geometry, daylight_analyzer=None):
        self.room = room_geometry
        self.polygon = room_geometry.polygon
        self.daylight = daylight_analyzer

        bounds = room_geometry.bounds
        self.min_x, self.min_y = bounds[0], bounds[1]
        self.max_x, self.max_y = bounds[2], bounds[3]
        self.room_w = self.max_x - self.min_x
        self.room_h = self.max_y - self.min_y
        self.room_cx, self.room_cy = room_geometry.centroid

        # Pre-compute wall segments
        self.walls = []
        for i, (start, end) in enumerate(room_geometry.walls):
            ws = WallSegment(
                i, start, end, self.polygon,
                room_geometry.doors, room_geometry.windows,
            )
            if ws.length > 0:
                self.walls.append(ws)

        # Pre-compute door exclusion zones
        self._door_zones = []
        for door in room_geometry.doors:
            zone = Point(door.position).buffer(DOOR_CLEARANCE_RADIUS).intersection(self.polygon)
            if not zone.is_empty:
                self._door_zones.append(zone)
        self._door_exclusion = unary_union(self._door_zones) if self._door_zones else Polygon()

    # ── Public API ──────────────────────────────────────────────────────

    def generate_variants(self, furniture_pieces, use_case="hybrid_flex", num_variants=4):
        """Generate multiple layout variants.

        Returns list of [(x, y, rotation), ...] placements, one per variant.
        Each variant uses a different placement strategy.
        """
        strategies = [
            {"wall_start": 0, "desk_dir": "inward", "meeting_pos": "center"},
            {"wall_start": 1, "desk_dir": "inward", "meeting_pos": "corner"},
            {"wall_start": 0, "desk_dir": "window", "meeting_pos": "center"},
            {"wall_start": 2, "desk_dir": "inward", "meeting_pos": "end"},
        ]

        results = []
        for i in range(min(num_variants, len(strategies))):
            placements = self._generate_layout(
                furniture_pieces, use_case, strategies[i]
            )
            results.append(placements)

        # If we need more, create rotated variants
        while len(results) < num_variants:
            strat = strategies[len(results) % len(strategies)].copy()
            strat["wall_start"] = len(results)
            placements = self._generate_layout(furniture_pieces, use_case, strat)
            results.append(placements)

        return results

    # ── Core Layout Generation ──────────────────────────────────────────

    def _generate_layout(self, pieces, use_case, strategy):
        """Generate a single complete layout using the given strategy."""
        placements = [(0, 0, 0)] * len(pieces)
        placed_polys = []

        # Categorize furniture
        desks = [(i, p) for i, p in enumerate(pieces) if p.category == "work_desk"]
        shared = [(i, p) for i, p in enumerate(pieces) if p.category == "shared_table"]
        meeting = [(i, p) for i, p in enumerate(pieces) if p.category == "meeting_table"]
        chairs = [(i, p) for i, p in enumerate(pieces) if p.category == "chair"]
        storage = [(i, p) for i, p in enumerate(pieces) if p.category == "storage"]
        lounge = [(i, p) for i, p in enumerate(pieces)
                  if p.category in ("lounge", "collaborative_seating")]

        # Rank walls for desk placement
        ranked_walls = self._rank_walls_for_desks(strategy)

        # 1. Place desks along walls (highest priority)
        desk_placements = self._place_desks_on_walls(
            desks, ranked_walls, placed_polys
        )
        for idx, pos in desk_placements.items():
            placements[idx] = pos

        # 2. Place chairs paired with desks
        chair_assignments = self._pair_chairs_with_desks(
            chairs, desks, placements, placed_polys
        )
        for idx, pos in chair_assignments.items():
            placements[idx] = pos

        # 3. Place meeting tables in open zones
        meeting_positions = self._place_meeting_tables(
            meeting, strategy, placed_polys
        )
        for idx, pos in meeting_positions.items():
            placements[idx] = pos

        # 4. Place shared tables
        shared_positions = self._place_shared_tables(
            shared, placed_polys
        )
        for idx, pos in shared_positions.items():
            placements[idx] = pos

        # 5. Place storage along walls (prefer short walls without windows)
        storage_positions = self._place_storage(
            storage, placed_polys
        )
        for idx, pos in storage_positions.items():
            placements[idx] = pos

        # 6. Place lounge near windows
        lounge_positions = self._place_lounge(
            lounge, placed_polys
        )
        for idx, pos in lounge_positions.items():
            placements[idx] = pos

        # 7. Place remaining meeting chairs around meeting tables
        remaining_chairs = [
            (i, p) for i, p in chairs if i not in chair_assignments
        ]
        if remaining_chairs and meeting:
            extra_chairs = self._place_meeting_chairs(
                remaining_chairs, meeting, placements, placed_polys
            )
            for idx, pos in extra_chairs.items():
                placements[idx] = pos

        return placements

    # ── Wall Ranking ────────────────────────────────────────────────────

    def _rank_walls_for_desks(self, strategy):
        """Rank walls for desk placement priority.

        Factors: length (longer = better), daylight (windows = better),
        no doors (uninterrupted = better).
        """
        scored = []
        wall_start_offset = strategy.get("wall_start", 0)
        prefer_window = strategy.get("desk_dir", "inward") == "window"

        for wall in self.walls:
            if wall.length < 120:  # Too short for any desk
                continue

            score = wall.length * 0.01  # Base: prefer longer walls

            if prefer_window and wall.has_window:
                score += 50  # Strong preference for window walls
            elif wall.has_window:
                score += 20  # Moderate preference

            if wall.has_door:
                score -= 30  # Penalize door walls (less usable length)

            score += wall.daylight_score * 30  # Daylight bonus

            scored.append((score, wall))

        # Sort by score descending, then rotate by strategy offset
        scored.sort(key=lambda x: x[0], reverse=True)

        if wall_start_offset > 0 and len(scored) > 1:
            offset = wall_start_offset % len(scored)
            scored = scored[offset:] + scored[:offset]

        return [w for _, w in scored]

    # ── Desk Placement ──────────────────────────────────────────────────

    def _place_desks_on_walls(self, desks, ranked_walls, placed_polys):
        """Place desks in rows along walls with uniform spacing and rotation."""
        result = {}
        desk_queue = list(desks)

        for wall in ranked_walls:
            if not desk_queue:
                break

            rotation = wall.desk_rotation()
            offset = DESK_WALL_GAP + 40  # Half desk depth + wall gap

            for t_lo, t_hi in wall.usable_ranges:
                if not desk_queue:
                    break

                # Calculate available linear length
                range_length = (t_hi - t_lo) * wall.length
                if range_length < 80:  # Too short
                    continue

                # Pack desks along this range
                t_cursor = t_lo
                while desk_queue and t_cursor < t_hi:
                    idx, piece = desk_queue[0]

                    # Space needed: half desk width + spacing from last desk
                    desk_half_w = piece.width / 2
                    needed_t = (desk_half_w + 10) / max(wall.length, 1)

                    if t_cursor + needed_t > t_hi:
                        break  # Not enough space

                    t_pos = t_cursor + needed_t
                    x = wall.start[0] + wall.ux * wall.length * t_pos
                    y = wall.start[1] + wall.uy * wall.length * t_pos

                    # Offset inward from wall
                    x += wall.nx * offset
                    y += wall.ny * offset

                    # Snap to grid
                    x = round(x / GRID_SNAP) * GRID_SNAP
                    y = round(y / GRID_SNAP) * GRID_SNAP

                    # Validate placement
                    test_poly = piece.get_polygon(x, y, rotation)
                    if (self.polygon.contains(test_poly) and
                            not self._collides(test_poly, placed_polys) and
                            not self._in_door_zone(test_poly)):

                        result[idx] = (x, y, rotation)
                        placed_polys.append(test_poly)
                        desk_queue.pop(0)

                        # Advance cursor by desk width + spacing
                        advance = (piece.width + WORKSTATION_SPACING) / max(wall.length, 1)
                        t_cursor = t_pos + advance - needed_t
                    else:
                        # Try next position
                        t_cursor += needed_t * 0.5
                        # Don't pop — try this desk at next position
                        if t_cursor + needed_t > t_hi:
                            break

        # Fallback: place remaining desks in grid near room center
        if desk_queue:
            self._place_in_grid(desk_queue, result, placed_polys)

        return result

    # ── Chair Pairing ───────────────────────────────────────────────────

    def _pair_chairs_with_desks(self, chairs, desks, placements, placed_polys):
        """Place chairs directly in front of each desk at a fixed offset."""
        result = {}
        chair_queue = list(chairs)

        for desk_idx, desk_piece in desks:
            if not chair_queue:
                break

            dx, dy, d_rot = placements[desk_idx]
            if dx == 0 and dy == 0 and d_rot == 0:
                continue  # Desk wasn't placed yet

            ci, chair_piece = chair_queue[0]

            # Chair goes in front of desk (front = positive Y direction of desk)
            rot_rad = math.radians(d_rot)
            front_offset = desk_piece.depth / 2 + CHAIR_PULLBACK

            # Front direction vector based on desk rotation
            cx = dx - math.sin(rot_rad) * front_offset
            cy = dy + math.cos(rot_rad) * front_offset

            # Snap to grid
            cx = round(cx / GRID_SNAP) * GRID_SNAP
            cy = round(cy / GRID_SNAP) * GRID_SNAP

            chair_rot = (d_rot + 180) % 360  # Face the desk

            test_poly = chair_piece.get_polygon(cx, cy, chair_rot)
            if self.polygon.contains(test_poly) and not self._collides(test_poly, placed_polys):
                result[ci] = (cx, cy, chair_rot)
                placed_polys.append(test_poly)
                chair_queue.pop(0)
            else:
                # Try offset positions
                for angle_off in [30, -30, 60, -60, 90, -90]:
                    alt_rad = rot_rad + math.radians(angle_off)
                    ax = dx - math.sin(alt_rad) * front_offset
                    ay = dy + math.cos(alt_rad) * front_offset
                    ax = round(ax / GRID_SNAP) * GRID_SNAP
                    ay = round(ay / GRID_SNAP) * GRID_SNAP

                    test_poly = chair_piece.get_polygon(ax, ay, chair_rot)
                    if self.polygon.contains(test_poly) and not self._collides(test_poly, placed_polys):
                        result[ci] = (ax, ay, chair_rot)
                        placed_polys.append(test_poly)
                        chair_queue.pop(0)
                        break

        return result

    # ── Meeting Tables ──────────────────────────────────────────────────

    def _place_meeting_tables(self, meeting_items, strategy, placed_polys):
        """Place meeting tables in open areas (center, corner, or end zones)."""
        result = {}
        if not meeting_items:
            return result

        position = strategy.get("meeting_pos", "center")

        for idx, piece in meeting_items:
            if position == "center":
                x, y = self.room_cx, self.room_cy
            elif position == "corner":
                x = self.min_x + self.room_w * 0.75
                y = self.min_y + self.room_h * 0.75
            else:  # "end"
                x = self.min_x + self.room_w * 0.5
                y = self.min_y + self.room_h * 0.8

            # Align to longest room dimension
            rotation = 0 if self.room_w > self.room_h else 90

            x = round(x / GRID_SNAP) * GRID_SNAP
            y = round(y / GRID_SNAP) * GRID_SNAP

            # Spiral out to find non-colliding position
            x, y = self._find_open_position(piece, x, y, rotation, placed_polys)

            result[idx] = (x, y, rotation)
            placed_polys.append(piece.get_polygon(x, y, rotation))

        return result

    # ── Shared Tables ───────────────────────────────────────────────────

    def _place_shared_tables(self, shared_items, placed_polys):
        """Place shared tables in work zone, slightly offset from center."""
        result = {}
        for i, (idx, piece) in enumerate(shared_items):
            # Distribute across room
            t = (i + 1) / (len(shared_items) + 1)
            x = self.min_x + self.room_w * (0.3 + t * 0.4)
            y = self.min_y + self.room_h * 0.4

            rotation = 0 if self.room_w > self.room_h else 90
            x = round(x / GRID_SNAP) * GRID_SNAP
            y = round(y / GRID_SNAP) * GRID_SNAP

            x, y = self._find_open_position(piece, x, y, rotation, placed_polys)
            result[idx] = (x, y, rotation)
            placed_polys.append(piece.get_polygon(x, y, rotation))

        return result

    # ── Storage ─────────────────────────────────────────────────────────

    def _place_storage(self, storage_items, placed_polys):
        """Place storage units against walls, preferring short walls without windows."""
        result = {}
        if not storage_items:
            return result

        # Rank walls: short walls without windows first
        ranked = sorted(
            self.walls,
            key=lambda w: (w.has_window, -w.has_door, w.length),
        )

        item_queue = list(storage_items)
        for wall in ranked:
            if not item_queue:
                break

            rotation = wall.desk_rotation()
            offset = DESK_WALL_GAP + 20  # Half storage depth

            for t_lo, t_hi in wall.usable_ranges:
                if not item_queue:
                    break

                t = (t_lo + t_hi) / 2
                idx, piece = item_queue[0]

                x = wall.start[0] + wall.ux * wall.length * t + wall.nx * offset
                y = wall.start[1] + wall.uy * wall.length * t + wall.ny * offset
                x = round(x / GRID_SNAP) * GRID_SNAP
                y = round(y / GRID_SNAP) * GRID_SNAP

                test_poly = piece.get_polygon(x, y, rotation)
                if (self.polygon.contains(test_poly) and
                        not self._collides(test_poly, placed_polys) and
                        not self._in_door_zone(test_poly)):
                    result[idx] = (x, y, rotation)
                    placed_polys.append(test_poly)
                    item_queue.pop(0)

        # Fallback for unplaced storage
        for idx, piece in item_queue:
            x, y = self._find_open_position(
                piece, self.room_cx, self.room_cy, 0, placed_polys
            )
            result[idx] = (x, y, 0)
            placed_polys.append(piece.get_polygon(x, y, 0))

        return result

    # ── Lounge / Collaborative ──────────────────────────────────────────

    def _place_lounge(self, lounge_items, placed_polys):
        """Place lounge furniture near windows for daylight access."""
        result = {}
        if not lounge_items:
            return result

        # Find window walls
        window_walls = [w for w in self.walls if w.has_window]
        if not window_walls:
            window_walls = self.walls[:1]  # Fallback to first wall

        for i, (idx, piece) in enumerate(lounge_items):
            wall = window_walls[i % len(window_walls)]
            rotation = wall.desk_rotation()

            # Place 150cm from window wall
            t = 0.5
            for t_lo, t_hi in wall.usable_ranges:
                t = (t_lo + t_hi) / 2
                break

            inward_offset = 150  # Further from wall than desks
            x = wall.start[0] + wall.ux * wall.length * t + wall.nx * inward_offset
            y = wall.start[1] + wall.uy * wall.length * t + wall.ny * inward_offset
            x = round(x / GRID_SNAP) * GRID_SNAP
            y = round(y / GRID_SNAP) * GRID_SNAP

            x, y = self._find_open_position(piece, x, y, rotation, placed_polys)
            result[idx] = (x, y, rotation)
            placed_polys.append(piece.get_polygon(x, y, rotation))

        return result

    # ── Meeting Chairs ──────────────────────────────────────────────────

    def _place_meeting_chairs(self, chair_items, meeting_items, placements, placed_polys):
        """Place remaining chairs around meeting tables."""
        result = {}
        if not chair_items or not meeting_items:
            return result

        chairs_per_table = max(1, len(chair_items) // len(meeting_items))

        ci = 0
        for mi, m_piece in meeting_items:
            mx, my, m_rot = placements[mi]

            for j in range(chairs_per_table):
                if ci >= len(chair_items):
                    break

                idx, chair_piece = chair_items[ci]
                angle = (j / chairs_per_table) * 2 * math.pi
                dist = max(m_piece.width, m_piece.depth) / 2 + 45

                cx = mx + math.cos(angle) * dist
                cy = my + math.sin(angle) * dist
                cx = round(cx / GRID_SNAP) * GRID_SNAP
                cy = round(cy / GRID_SNAP) * GRID_SNAP
                c_rot = round(math.degrees(angle + math.pi) / 90) * 90 % 360

                test_poly = chair_piece.get_polygon(cx, cy, c_rot)
                if self.polygon.contains(test_poly) and not self._collides(test_poly, placed_polys):
                    result[idx] = (cx, cy, c_rot)
                    placed_polys.append(test_poly)
                ci += 1

        return result

    # ── Grid Fallback ───────────────────────────────────────────────────

    def _place_in_grid(self, item_queue, result, placed_polys):
        """Place remaining items in a grid pattern near room center."""
        n = len(item_queue)
        if n == 0:
            return

        cols = max(1, int(math.sqrt(n)))
        rows = math.ceil(n / cols)
        margin = 100

        dx = (self.room_w - margin * 2) / max(cols, 1)
        dy = (self.room_h - margin * 2) / max(rows, 1)

        for k, (idx, piece) in enumerate(item_queue):
            col = k % cols
            row = k // cols
            x = self.min_x + margin + dx * (col + 0.5)
            y = self.min_y + margin + dy * (row + 0.5)

            x = round(x / GRID_SNAP) * GRID_SNAP
            y = round(y / GRID_SNAP) * GRID_SNAP

            rotation = 0

            x, y = self._find_open_position(piece, x, y, rotation, placed_polys)
            result[idx] = (x, y, rotation)
            placed_polys.append(piece.get_polygon(x, y, rotation))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _find_open_position(self, piece, x, y, rotation, placed_polys, max_attempts=30):
        """Spiral outward from (x, y) to find a collision-free position."""
        for attempt in range(max_attempts):
            test_poly = piece.get_polygon(x, y, rotation)
            if (self.polygon.contains(test_poly) and
                    not self._collides(test_poly, placed_polys) and
                    not self._in_door_zone(test_poly)):
                return x, y

            # Spiral out
            angle = attempt * 0.8
            radius = 40 + attempt * 25
            x2 = x + math.cos(angle) * radius
            y2 = y + math.sin(angle) * radius
            x2 = round(x2 / GRID_SNAP) * GRID_SNAP
            y2 = round(y2 / GRID_SNAP) * GRID_SNAP

            # Check candidate
            test_poly = piece.get_polygon(x2, y2, rotation)
            if (self.polygon.contains(test_poly) and
                    not self._collides(test_poly, placed_polys) and
                    not self._in_door_zone(test_poly)):
                return x2, y2

        # Clamp to room center as last resort
        return self._clamp_to_room(x, y, piece, rotation)

    def _collides(self, poly, placed_polys):
        """Check if polygon collides with any placed polygon."""
        for pp in placed_polys:
            if poly.intersects(pp):
                return True
        return False

    def _in_door_zone(self, poly):
        """Check if polygon overlaps a door clearance zone."""
        if self._door_exclusion.is_empty:
            return False
        return poly.intersects(self._door_exclusion)

    def _clamp_to_room(self, x, y, piece, rotation):
        """Ensure furniture is inside the room polygon."""
        test = piece.get_polygon(x, y, rotation)
        if self.polygon.contains(test):
            return x, y

        # Move toward centroid
        for factor in [0.2, 0.4, 0.6, 0.8, 0.95]:
            nx = x + (self.room_cx - x) * factor
            ny = y + (self.room_cy - y) * factor
            nx = round(nx / GRID_SNAP) * GRID_SNAP
            ny = round(ny / GRID_SNAP) * GRID_SNAP
            test = piece.get_polygon(nx, ny, rotation)
            if self.polygon.contains(test):
                return nx, ny

        return round(self.room_cx / GRID_SNAP) * GRID_SNAP, round(self.room_cy / GRID_SNAP) * GRID_SNAP
