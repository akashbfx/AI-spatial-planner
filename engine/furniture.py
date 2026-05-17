"""
Furniture models and catalog management.
"""

import json
import os
import math
from shapely.geometry import Polygon
from shapely.affinity import rotate, translate


# Furniture categories with their properties
CATEGORY_PROPERTIES = {
    "work_desk": {
        "label": "Work Desk",
        "color": "#4A90D9",
        "wall_affinity": 0.8,
        "window_affinity": 0.7,
        "group_affinity": 0.5,
        "default_clearance_front": 80,
        "default_clearance_sides": 10,
        "default_clearance_back": 5,
        "height_3d": 75,
    },
    "shared_table": {
        "label": "Shared Table",
        "color": "#50B86C",
        "wall_affinity": 0.2,
        "window_affinity": 0.5,
        "group_affinity": 0.9,
        "default_clearance_front": 80,
        "default_clearance_sides": 80,
        "default_clearance_back": 80,
        "height_3d": 75,
    },
    "meeting_table": {
        "label": "Meeting Table",
        "color": "#E8833A",
        "wall_affinity": 0.3,
        "window_affinity": 0.4,
        "group_affinity": 0.3,
        "default_clearance_front": 80,
        "default_clearance_sides": 80,
        "default_clearance_back": 80,
        "height_3d": 75,
    },
    "chair": {
        "label": "Chair",
        "color": "#9B59B6",
        "wall_affinity": 0.1,
        "window_affinity": 0.3,
        "group_affinity": 0.8,
        "default_clearance_front": 60,
        "default_clearance_sides": 5,
        "default_clearance_back": 5,
        "height_3d": 85,
    },
    "storage": {
        "label": "Storage Unit",
        "color": "#7F8C8D",
        "wall_affinity": 1.0,
        "window_affinity": 0.0,
        "group_affinity": 0.2,
        "default_clearance_front": 70,
        "default_clearance_sides": 0,
        "default_clearance_back": 0,
        "height_3d": 180,
    },
    "collaborative_seating": {
        "label": "Collaborative Seating",
        "color": "#1ABC9C",
        "wall_affinity": 0.5,
        "window_affinity": 0.6,
        "group_affinity": 0.9,
        "default_clearance_front": 60,
        "default_clearance_sides": 30,
        "default_clearance_back": 10,
        "height_3d": 45,
    },
    "lounge": {
        "label": "Lounge Furniture",
        "color": "#E74C3C",
        "wall_affinity": 0.6,
        "window_affinity": 0.8,
        "group_affinity": 0.7,
        "default_clearance_front": 50,
        "default_clearance_sides": 20,
        "default_clearance_back": 5,
        "height_3d": 70,
    },
}


class FurniturePiece:
    """Represents a single furniture item with dimensions and properties."""

    def __init__(self, id, name, category, width, depth, height=75,
                 clearance_front=None, clearance_sides=None, clearance_back=None,
                 wall_affinity=None, window_affinity=None, group_affinity=None,
                 is_custom=False):
        self.id = id
        self.name = name
        self.category = category
        self.width = width  # cm (along x-axis at rotation=0)
        self.depth = depth  # cm (along y-axis at rotation=0)
        self.height = height  # cm
        self.is_custom = is_custom

        # Get category defaults
        cat_props = CATEGORY_PROPERTIES.get(category, {})

        self.clearance_front = clearance_front if clearance_front is not None else cat_props.get("default_clearance_front", 60)
        self.clearance_sides = clearance_sides if clearance_sides is not None else cat_props.get("default_clearance_sides", 10)
        self.clearance_back = clearance_back if clearance_back is not None else cat_props.get("default_clearance_back", 5)

        self.wall_affinity = wall_affinity if wall_affinity is not None else cat_props.get("wall_affinity", 0.5)
        self.window_affinity = window_affinity if window_affinity is not None else cat_props.get("window_affinity", 0.5)
        self.group_affinity = group_affinity if group_affinity is not None else cat_props.get("group_affinity", 0.5)

        self.color = cat_props.get("color", "#888888")
        self.height_3d = cat_props.get("height_3d", height)

    def get_polygon(self, x, y, rotation=0):
        """Get furniture footprint as Shapely Polygon at given position and rotation.

        Args:
            x, y: Center position (cm)
            rotation: Rotation in degrees (0, 90, 180, 270)

        Returns:
            Shapely Polygon
        """
        hw = self.width / 2
        hd = self.depth / 2
        rect = Polygon([
            (-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)
        ])
        rotated = rotate(rect, rotation, origin=(0, 0))
        return translate(rotated, x, y)

    def get_clearance_polygon(self, x, y, rotation=0):
        """Get furniture footprint including clearance zones.

        Returns:
            Shapely Polygon with clearance buffer
        """
        hw = self.width / 2 + self.clearance_sides
        hd_front = self.depth / 2 + self.clearance_front
        hd_back = self.depth / 2 + self.clearance_back
        rect = Polygon([
            (-hw, -hd_back), (hw, -hd_back), (hw, hd_front), (-hw, hd_front)
        ])
        rotated = rotate(rect, rotation, origin=(0, 0))
        return translate(rotated, x, y)

    def get_footprint_area(self):
        """Furniture footprint area in sq cm."""
        return self.width * self.depth

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "clearance_front": self.clearance_front,
            "clearance_sides": self.clearance_sides,
            "clearance_back": self.clearance_back,
            "wall_affinity": self.wall_affinity,
            "window_affinity": self.window_affinity,
            "group_affinity": self.group_affinity,
            "color": self.color,
            "is_custom": self.is_custom,
        }


class FurnitureCatalog:
    """Manages the furniture catalog with default and custom pieces."""

    def __init__(self, catalog_path=None):
        self.pieces = {}
        self._next_custom_id = 1000

        if catalog_path and os.path.exists(catalog_path):
            self.load_catalog(catalog_path)

    def load_catalog(self, path):
        """Load furniture catalog from JSON file."""
        with open(path, "r") as f:
            data = json.load(f)

        for item in data.get("furniture", []):
            piece = FurniturePiece(
                id=item["id"],
                name=item["name"],
                category=item["category"],
                width=item["width"],
                depth=item["depth"],
                height=item.get("height", 75),
                clearance_front=item.get("clearance_front"),
                clearance_sides=item.get("clearance_sides"),
                clearance_back=item.get("clearance_back"),
            )
            self.pieces[piece.id] = piece

    def add_custom(self, name, category, width, depth, height=75,
                   clearance_front=None, clearance_sides=None, clearance_back=None):
        """Add a custom furniture piece."""
        pid = f"custom_{self._next_custom_id}"
        self._next_custom_id += 1

        piece = FurniturePiece(
            id=pid, name=name, category=category,
            width=width, depth=depth, height=height,
            clearance_front=clearance_front,
            clearance_sides=clearance_sides,
            clearance_back=clearance_back,
            is_custom=True,
        )
        self.pieces[pid] = piece
        return piece

    def get_piece(self, piece_id):
        """Get a furniture piece by ID."""
        return self.pieces.get(piece_id)

    def get_by_category(self, category):
        """Get all pieces in a category."""
        return [p for p in self.pieces.values() if p.category == category]

    def get_categories(self):
        """Get available categories with labels."""
        return {k: v["label"] for k, v in CATEGORY_PROPERTIES.items()}

    def to_dict(self):
        return {
            "furniture": [p.to_dict() for p in self.pieces.values()],
            "categories": self.get_categories(),
        }
