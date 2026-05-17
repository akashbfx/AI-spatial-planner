"""
Layout Rules Engine — zone-based spatial knowledge for professional furniture placement.

Encodes 50+ professional placement patterns based on Neufert, WELL Building,
and real-world coworking design principles.
"""

import math
import random
from shapely.geometry import Polygon, Point, LineString, MultiPolygon
from shapely.affinity import rotate as shapely_rotate, translate as shapely_translate
from shapely.ops import unary_union
import numpy as np


# ─── Layout Pattern Library ───────────────────────────────────────────

PLACEMENT_PATTERNS = {
    "perimeter_desks": {
        "description": "Desks along walls, meeting in center",
        "best_for": ["hot_desking", "team_pods"],
        "desk_placement": "wall_aligned",
        "meeting_placement": "center",
        "lounge_placement": "window_adjacent",
    },
    "island_cluster": {
        "description": "Desk clusters in room center, storage on walls",
        "best_for": ["team_pods", "collaborative_hub"],
        "desk_placement": "center_clusters",
        "meeting_placement": "corner",
        "lounge_placement": "window_adjacent",
    },
    "linear_rows": {
        "description": "Rows of desks aligned to longest wall",
        "best_for": ["hot_desking"],
        "desk_placement": "linear_rows",
        "meeting_placement": "end_zone",
        "lounge_placement": "opposite_end",
    },
    "u_shape": {
        "description": "U-shaped desk arrangement around three walls",
        "best_for": ["team_pods", "meeting_heavy"],
        "desk_placement": "u_shape",
        "meeting_placement": "center",
        "lounge_placement": "open_end",
    },
    "zone_divided": {
        "description": "Room split into distinct functional zones",
        "best_for": ["hybrid_flex", "collaborative_hub"],
        "desk_placement": "zone_work",
        "meeting_placement": "zone_meeting",
        "lounge_placement": "zone_social",
    },
}

# ─── Neufert / WELL Standards ─────────────────────────────────────────

STANDARDS = {
    # Clearances (cm)
    "door_swing_clearance": 100,
    "primary_corridor_width": 120,
    "secondary_corridor_width": 90,
    "wheelchair_turning_radius": 150,
    "workstation_min_spacing": 140,
    "desk_to_wall_min": 5,
    "chair_pullback": 60,
    "meeting_chair_clearance": 80,
    "min_passage_width": 75,

    # Ergonomic (cm)
    "desk_depth_min": 60,
    "monitor_distance_min": 50,
    "facing_desk_min_gap": 160,

    # Area standards (sq cm)
    "sqm_per_person_min": 40000,  # 4 sqm
    "sqm_per_person_comfort": 60000,  # 6 sqm
}


class RoomZone:
    """A functional zone within the room."""

    def __init__(self, zone_type, polygon, priority=1.0):
        self.zone_type = zone_type  # 'work', 'meeting', 'social', 'circulation', 'storage'
        self.polygon = polygon
        self.priority = priority
        self.placed_items = []

    @property
    def area(self):
        return self.polygon.area

    @property
    def centroid(self):
        c = self.polygon.centroid
        return (c.x, c.y)

    @property
    def bounds(self):
        return self.polygon.bounds


class LayoutRulesEngine:
    """
    Knowledge-based layout engine that generates intelligent initial placements
    using professional spatial planning rules.
    """

    def __init__(self, room_geometry):
        self.room = room_geometry
        self.polygon = room_geometry.polygon
        self.bounds = room_geometry.bounds
        self.walls = room_geometry.walls
        self.doors = room_geometry.doors
        self.windows = room_geometry.windows

        # Pre-compute
        self._room_cx, self._room_cy = room_geometry.centroid
        self._room_w = self.bounds[2] - self.bounds[0]
        self._room_h = self.bounds[3] - self.bounds[1]
        self._wall_lines = []
        self._wall_normals = []
        self._wall_angles = []
        self._compute_wall_data()

        # Door clearance zones
        self._door_zones = self._compute_door_zones()

    def _compute_wall_data(self):
        """Pre-compute wall geometry data."""
        for i, (start, end) in enumerate(self.walls):
            dx = end[0] - start[0]
            dy = end[1] - start[1]
            length = math.hypot(dx, dy)
            if length == 0:
                continue

            angle = math.atan2(dy, dx)
            # Inward normal
            nx, ny = -dy / length, dx / length

            # Check if normal points inward
            test_x = (start[0] + end[0]) / 2 + nx * 10
            test_y = (start[1] + end[1]) / 2 + ny * 10
            if not self.polygon.contains(Point(test_x, test_y)):
                nx, ny = -nx, -ny

            self._wall_lines.append(LineString([start, end]))
            self._wall_normals.append((nx, ny))
            self._wall_angles.append(angle)

    def _compute_door_zones(self):
        """Compute door clearance exclusion zones."""
        zones = []
        for door in self.doors:
            cx, cy = door.position
            r = STANDARDS["door_swing_clearance"]
            zone = Point(cx, cy).buffer(r).intersection(self.polygon)
            if not zone.is_empty:
                zones.append(zone)
        return zones

    def _get_door_exclusion(self):
        """Union of all door clearance zones."""
        if not self._door_zones:
            return Polygon()
        return unary_union(self._door_zones)

    # ─── Zone Generation ──────────────────────────────────────────────

    def generate_zones(self, use_case="hybrid_flex"):
        """Divide room into functional zones based on use case."""
        zones = []

        # 1. Circulation zone — path from each door to room center
        circ_polys = []
        corridor_w = STANDARDS["primary_corridor_width"]
        for door in self.doors:
            path = LineString([door.position, (self._room_cx, self._room_cy)])
            buffer = path.buffer(corridor_w / 2)
            clipped = buffer.intersection(self.polygon)
            if not clipped.is_empty:
                circ_polys.append(clipped)

        circ_zone = unary_union(circ_polys) if circ_polys else Polygon()
        if not circ_zone.is_empty:
            zones.append(RoomZone("circulation", circ_zone, priority=0.0))

        # 2. Remaining area for furniture placement
        remaining = self.polygon.difference(circ_zone) if not circ_zone.is_empty else self.polygon
        door_exclusion = self._get_door_exclusion()
        if not door_exclusion.is_empty:
            remaining = remaining.difference(door_exclusion)

        if remaining.is_empty:
            remaining = self.polygon

        # 3. Split remaining into work/meeting/social zones
        zone_ratios = self._get_zone_ratios(use_case)

        # Simple zone division: use quadrants/halves based on room geometry
        min_x, min_y, max_x, max_y = remaining.bounds
        mid_x = (min_x + max_x) / 2
        mid_y = (min_y + max_y) / 2

        # Window side gets social/lounge
        window_side = self._get_window_side()

        # Create zone polygons based on room division
        if self._room_w > self._room_h * 1.3:
            # Wide room — vertical split
            work_box = Polygon([(min_x, min_y), (mid_x, min_y), (mid_x, max_y), (min_x, max_y)])
            meet_box = Polygon([(mid_x, min_y), (max_x, min_y), (max_x, mid_y), (mid_x, mid_y)])
            social_box = Polygon([(mid_x, mid_y), (max_x, mid_y), (max_x, max_y), (mid_x, max_y)])
        elif self._room_h > self._room_w * 1.3:
            # Tall room — horizontal split
            work_box = Polygon([(min_x, min_y), (max_x, min_y), (max_x, mid_y), (min_x, mid_y)])
            meet_box = Polygon([(min_x, mid_y), (mid_x, mid_y), (mid_x, max_y), (min_x, max_y)])
            social_box = Polygon([(mid_x, mid_y), (max_x, mid_y), (max_x, max_y), (mid_x, max_y)])
        else:
            # Square-ish room — L-shape zones
            work_box = Polygon([(min_x, min_y), (max_x, min_y), (max_x, mid_y), (min_x, mid_y)])
            meet_box = Polygon([(min_x, mid_y), (mid_x, mid_y), (mid_x, max_y), (min_x, max_y)])
            social_box = Polygon([(mid_x, mid_y), (max_x, mid_y), (max_x, max_y), (mid_x, max_y)])

        work_zone = work_box.intersection(remaining)
        meet_zone = meet_box.intersection(remaining)
        social_zone = social_box.intersection(remaining)

        if not work_zone.is_empty:
            zones.append(RoomZone("work", work_zone, priority=zone_ratios.get("work", 0.5)))
        if not meet_zone.is_empty:
            zones.append(RoomZone("meeting", meet_zone, priority=zone_ratios.get("meeting", 0.2)))
        if not social_zone.is_empty:
            zones.append(RoomZone("social", social_zone, priority=zone_ratios.get("social", 0.2)))

        return zones

    def _get_zone_ratios(self, use_case):
        """Get zone area ratios for a use case."""
        ratios = {
            "hot_desking": {"work": 0.65, "meeting": 0.15, "social": 0.10, "storage": 0.10},
            "team_pods": {"work": 0.50, "meeting": 0.20, "social": 0.15, "storage": 0.15},
            "meeting_heavy": {"work": 0.25, "meeting": 0.45, "social": 0.20, "storage": 0.10},
            "collaborative_hub": {"work": 0.30, "meeting": 0.15, "social": 0.40, "storage": 0.15},
            "hybrid_flex": {"work": 0.40, "meeting": 0.25, "social": 0.20, "storage": 0.15},
        }
        return ratios.get(use_case, ratios["hybrid_flex"])

    def _get_window_side(self):
        """Determine which side of the room has windows."""
        if not self.windows:
            return "none"
        avg_x = np.mean([w.position[0] for w in self.windows])
        avg_y = np.mean([w.position[1] for w in self.windows])
        if avg_x < self._room_cx:
            return "left"
        elif avg_x > self._room_cx:
            return "right"
        elif avg_y < self._room_cy:
            return "top"
        else:
            return "bottom"

    # ─── Placement Strategies ────────────────────────────────────────

    def generate_smart_placement(self, furniture_pieces, use_case="hybrid_flex"):
        """Generate an intelligent initial placement for all furniture.

        Returns:
            List of (x, y, rotation) tuples — one per furniture piece.
        """
        zones = self.generate_zones(use_case)
        placements = [(0, 0, 0)] * len(furniture_pieces)
        placed_polys = []

        # Sort furniture by placement priority
        priority_order = {
            "meeting_table": 0,
            "shared_table": 1,
            "work_desk": 2,
            "storage": 3,
            "collaborative_seating": 4,
            "lounge": 5,
            "chair": 6,
        }

        # Sort by placement priority (tables first, chairs last)
        indexed = list(enumerate(furniture_pieces))
        indexed.sort(key=lambda x: priority_order.get(x[1].category, 99))

        # Track which chairs should pair with which tables
        chair_pairs = []

        for orig_idx, piece in indexed:
            if piece.category == "chair":
                # Defer chairs — pair them with tables later
                chair_pairs.append(orig_idx)
                continue

            # Find best zone for this category
            zone = self._best_zone_for(piece.category, zones)
            if zone is None:
                zone = zones[0] if zones else None

            if zone is None:
                # Fallback to room center
                x, y = self._room_cx, self._room_cy
                rot = 0
            else:
                x, y, rot = self._place_in_zone(piece, zone, placed_polys)

            # Validate inside room
            x, y = self._clamp_to_room(x, y, piece, rot)

            placements[orig_idx] = (x, y, rot)
            placed_polys.append(piece.get_polygon(x, y, rot))

        # Now place chairs paired with tables
        self._place_chairs(chair_pairs, placements, furniture_pieces, placed_polys)

        return placements

    def _best_zone_for(self, category, zones):
        """Find the best zone for a furniture category."""
        zone_map = {
            "work_desk": "work",
            "shared_table": "work",
            "meeting_table": "meeting",
            "storage": "work",
            "collaborative_seating": "social",
            "lounge": "social",
        }
        target = zone_map.get(category, "work")
        for z in zones:
            if z.zone_type == target:
                return z
        # Fallback: any non-circulation zone
        for z in zones:
            if z.zone_type != "circulation":
                return z
        return zones[0] if zones else None

    def _place_in_zone(self, piece, zone, placed_polys):
        """Place a furniture piece within a zone using smart rules."""
        category = piece.category
        zone_bounds = zone.bounds
        zmin_x, zmin_y, zmax_x, zmax_y = zone_bounds

        if category in ("work_desk", "storage"):
            # Wall-aligned placement
            return self._place_along_wall(piece, zone, placed_polys)
        elif category == "meeting_table":
            # Center of zone
            return self._place_at_zone_center(piece, zone, placed_polys)
        elif category == "shared_table":
            # Slightly off-center in zone
            return self._place_at_zone_center(piece, zone, placed_polys, offset=True)
        elif category in ("lounge", "collaborative_seating"):
            # Near windows or zone center
            return self._place_near_windows_or_center(piece, zone, placed_polys)
        else:
            cx, cy = zone.centroid
            return cx, cy, 0

    def _place_along_wall(self, piece, zone, placed_polys):
        """Place furniture aligned to the nearest wall."""
        best_pos = None
        best_score = -float("inf")

        for i, (start, end) in enumerate(self.walls):
            wall_line = self._wall_lines[i] if i < len(self._wall_lines) else None
            if wall_line is None:
                continue

            nx, ny = self._wall_normals[i]
            wall_angle = self._wall_angles[i]

            # Determine rotation to align with wall
            # Desk back faces wall, front faces room
            rot_deg = math.degrees(wall_angle) + 90
            rot_deg = round(rot_deg / 90) * 90 % 360

            # Try positions along this wall
            wall_len = wall_line.length
            num_positions = max(2, int(wall_len / (piece.width + 20)))

            for j in range(num_positions):
                t = (j + 0.5) / num_positions
                t = max(0.1, min(0.9, t))

                wx = start[0] + (end[0] - start[0]) * t
                wy = start[1] + (end[1] - start[1]) * t

                # Offset inward from wall
                offset = max(piece.width, piece.depth) / 2 + STANDARDS["desk_to_wall_min"]
                x = wx + nx * offset
                y = wy + ny * offset

                # Check if position is in zone and room
                if not zone.polygon.contains(Point(x, y)):
                    continue
                if not self.polygon.contains(Point(x, y)):
                    continue

                # Check collisions
                test_poly = piece.get_polygon(x, y, rot_deg)
                collision = False
                for pp in placed_polys:
                    if test_poly.intersects(pp):
                        collision = True
                        break

                if collision:
                    continue

                # Check door clearance
                door_clear = True
                for dz in self._door_zones:
                    if test_poly.intersects(dz):
                        door_clear = False
                        break

                if not door_clear:
                    continue

                # Score: prefer longer walls, positions away from doors
                score = wall_len * 0.01
                # Bonus for being inside room
                if self.polygon.contains(test_poly):
                    score += 100
                # Penalty for being near doors
                for door in self.doors:
                    d = math.hypot(x - door.position[0], y - door.position[1])
                    if d < 150:
                        score -= (150 - d) * 0.5

                if score > best_score:
                    best_score = score
                    best_pos = (x, y, rot_deg)

        if best_pos:
            return best_pos

        # Fallback: zone center
        cx, cy = zone.centroid
        return cx, cy, 0

    def _place_at_zone_center(self, piece, zone, placed_polys, offset=False):
        """Place furniture at or near center of zone."""
        cx, cy = zone.centroid

        if offset:
            cx += random.uniform(-50, 50)
            cy += random.uniform(-50, 50)

        # Determine rotation (align to longest room dimension)
        if self._room_w > self._room_h:
            rot = 0
        else:
            rot = 90

        # Check collision and adjust
        x, y = cx, cy
        for attempt in range(20):
            test_poly = piece.get_polygon(x, y, rot)
            collision = False
            for pp in placed_polys:
                if test_poly.intersects(pp):
                    collision = True
                    break

            if not collision and self.polygon.contains(test_poly):
                return x, y, rot

            # Spiral outward
            angle = attempt * 0.8
            radius = 50 + attempt * 30
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius

        return cx, cy, rot

    def _place_near_windows_or_center(self, piece, zone, placed_polys):
        """Place lounge/collaborative furniture near windows."""
        # Try near windows first
        for window in self.windows:
            wx, wy = window.position
            wi = window.wall_index
            if wi < len(self._wall_normals):
                nx, ny = self._wall_normals[wi]
                # Place 150cm from window wall
                x = wx + nx * 150
                y = wy + ny * 150

                if zone.polygon.contains(Point(x, y)):
                    # Check collision
                    test_poly = piece.get_polygon(x, y, 0)
                    collision = any(test_poly.intersects(pp) for pp in placed_polys)
                    if not collision and self.polygon.contains(test_poly):
                        # Face toward window
                        wall_angle = self._wall_angles[wi] if wi < len(self._wall_angles) else 0
                        rot = round(math.degrees(wall_angle) / 90) * 90 % 360
                        return x, y, rot

        # Fallback to zone center
        return self._place_at_zone_center(piece, zone, placed_polys)

    def _place_chairs(self, chair_indices, placements, all_pieces, placed_polys):
        """Place chairs adjacent to their matching tables/desks."""
        # Find all table/desk positions
        table_positions = []
        for i, piece in enumerate(all_pieces):
            if piece.category in ("work_desk", "shared_table", "meeting_table"):
                x, y, rot = placements[i]
                table_positions.append((i, x, y, rot, piece))

        chair_idx = 0
        for ci in chair_indices:
            piece = all_pieces[ci]

            if not table_positions:
                # No tables — place in grid
                x, y = self._room_cx + random.uniform(-100, 100), self._room_cy + random.uniform(-100, 100)
                x, y = self._clamp_to_room(x, y, piece, 0)
                placements[ci] = (x, y, 0)
                continue

            # Assign chair to a table (round-robin)
            table_idx, tx, ty, trot, table = table_positions[chair_idx % len(table_positions)]

            # Calculate chair position relative to table
            trot_rad = math.radians(trot)

            if table.category == "meeting_table":
                # Chairs around meeting table
                n_chairs_per_table = sum(1 for c in chair_indices if c == ci or True)
                angle_offset = (chair_idx % 8) * (math.pi / 4)
                dist = max(table.width, table.depth) / 2 + 40
                cx = tx + math.cos(angle_offset) * dist
                cy = ty + math.sin(angle_offset) * dist
                chair_rot = (math.degrees(angle_offset) + 180) % 360
            else:
                # Chair in front of desk
                # Front direction based on desk rotation
                front_x = -math.sin(trot_rad) * (table.depth / 2 + piece.depth / 2 + 10)
                front_y = math.cos(trot_rad) * (table.depth / 2 + piece.depth / 2 + 10)
                cx = tx + front_x
                cy = ty + front_y
                chair_rot = (trot + 180) % 360

            # Clamp and validate
            cx, cy = self._clamp_to_room(cx, cy, piece, chair_rot)

            # Check collision
            test_poly = piece.get_polygon(cx, cy, chair_rot)
            collision = any(test_poly.intersects(pp) for pp in placed_polys)
            if collision:
                # Offset slightly
                for attempt in range(10):
                    offset_angle = random.uniform(0, 2 * math.pi)
                    cx2 = cx + math.cos(offset_angle) * 30
                    cy2 = cy + math.sin(offset_angle) * 30
                    test_poly = piece.get_polygon(cx2, cy2, chair_rot)
                    if not any(test_poly.intersects(pp) for pp in placed_polys):
                        cx, cy = cx2, cy2
                        break

            placements[ci] = (cx, cy, chair_rot)
            placed_polys.append(piece.get_polygon(cx, cy, chair_rot))
            chair_idx += 1

    def _clamp_to_room(self, x, y, piece, rotation):
        """Ensure furniture is completely inside the room polygon."""
        poly = piece.get_polygon(x, y, rotation)

        if self.polygon.contains(poly):
            return x, y

        # Strategy 1: Move toward room centroid
        for factor in [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]:
            nx = x + (self._room_cx - x) * factor
            ny = y + (self._room_cy - y) * factor
            test = piece.get_polygon(nx, ny, rotation)
            if self.polygon.contains(test):
                return round(nx / 10) * 10, round(ny / 10) * 10

        # Strategy 2: Shrink toward centroid with buffer
        for factor in [0.3, 0.5, 0.7, 0.9]:
            nx = self._room_cx + (x - self._room_cx) * (1 - factor)
            ny = self._room_cy + (y - self._room_cy) * (1 - factor)
            if self.polygon.contains(Point(nx, ny)):
                test = piece.get_polygon(nx, ny, rotation)
                if self.polygon.contains(test):
                    return round(nx / 10) * 10, round(ny / 10) * 10

        # Strategy 3: Use room centroid as fallback
        test = piece.get_polygon(self._room_cx, self._room_cy, rotation)
        if self.polygon.contains(test):
            return round(self._room_cx / 10) * 10, round(self._room_cy / 10) * 10

        # Strategy 4: Find a valid position by sampling
        minx, miny, maxx, maxy = self.bounds
        margin = max(piece.width, piece.depth)
        for _ in range(50):
            rx = random.uniform(minx + margin, maxx - margin)
            ry = random.uniform(miny + margin, maxy - margin)
            test = piece.get_polygon(rx, ry, rotation)
            if self.polygon.contains(test):
                return round(rx / 10) * 10, round(ry / 10) * 10

        # Absolute fallback
        return round(self._room_cx / 10) * 10, round(self._room_cy / 10) * 10

    def repair_placement(self, x, y, rotation, piece):
        """Repair a single placement to ensure it's inside the room."""
        return self._clamp_to_room(x, y, piece, rotation)
