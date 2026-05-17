"""
Smart suggest engine — auto-recommends furniture for coworking use cases.
"""

import math


# Coworking use-case templates
COWORKING_TEMPLATES = {
    "hot_desking": {
        "label": "Hot Desking",
        "description": "Maximize individual workstations for flexible seating. Ideal for freelancers and remote workers.",
        "density": "high",
        "furniture_ratios": {
            "work_desk": 0.45,
            "chair": 0.30,
            "storage": 0.10,
            "shared_table": 0.05,
            "lounge": 0.05,
            "collaborative_seating": 0.05,
        },
        "sqm_per_person": 4.5,
    },
    "team_pods": {
        "label": "Team Pods",
        "description": "Groups of 4-6 desks with shared work tables. Best for startup teams and project groups.",
        "density": "medium",
        "furniture_ratios": {
            "work_desk": 0.30,
            "shared_table": 0.20,
            "chair": 0.25,
            "storage": 0.08,
            "collaborative_seating": 0.10,
            "lounge": 0.07,
        },
        "sqm_per_person": 5.5,
    },
    "meeting_heavy": {
        "label": "Meeting Heavy",
        "description": "Prioritize meeting and conference areas with breakout spaces. For consulting and client-facing work.",
        "density": "medium",
        "furniture_ratios": {
            "meeting_table": 0.25,
            "chair": 0.30,
            "work_desk": 0.15,
            "shared_table": 0.10,
            "storage": 0.05,
            "lounge": 0.15,
        },
        "sqm_per_person": 6.0,
    },
    "collaborative_hub": {
        "label": "Collaborative Hub",
        "description": "Shared tables and lounge seating for creative collaboration. Ideal for design studios and innovation labs.",
        "density": "low",
        "furniture_ratios": {
            "shared_table": 0.25,
            "collaborative_seating": 0.20,
            "lounge": 0.20,
            "work_desk": 0.10,
            "chair": 0.15,
            "storage": 0.05,
            "meeting_table": 0.05,
        },
        "sqm_per_person": 7.0,
    },
    "hybrid_flex": {
        "label": "Hybrid Flex",
        "description": "Balanced mix of all workspace types for maximum flexibility. Supports diverse work styles.",
        "density": "medium",
        "furniture_ratios": {
            "work_desk": 0.22,
            "shared_table": 0.15,
            "meeting_table": 0.10,
            "chair": 0.23,
            "storage": 0.08,
            "collaborative_seating": 0.12,
            "lounge": 0.10,
        },
        "sqm_per_person": 5.5,
    },
}

# Default furniture dimensions per category (cm)
DEFAULT_DIMENSIONS = {
    "work_desk": {"width": 120, "depth": 60},
    "shared_table": {"width": 200, "depth": 100},
    "meeting_table": {"width": 240, "depth": 120},
    "chair": {"width": 50, "depth": 50},
    "storage": {"width": 80, "depth": 40},
    "collaborative_seating": {"width": 180, "depth": 50},
    "lounge": {"width": 80, "depth": 80},
}

# Clearance multipliers for area calculation
CLEARANCE_AREA = {
    "work_desk": 1.8,  # desk + chair pullback space
    "shared_table": 2.5,
    "meeting_table": 3.0,
    "chair": 1.3,
    "storage": 1.4,
    "collaborative_seating": 1.8,
    "lounge": 1.6,
}


class SmartSuggestEngine:
    """Analyzes room and suggests optimal furniture configurations."""

    def __init__(self, room_geometry, furniture_catalog=None):
        self.room = room_geometry
        self.catalog = furniture_catalog

    def suggest_for_use_case(self, use_case="hybrid_flex"):
        """Suggest furniture quantities for a given coworking use case.

        Args:
            use_case: One of the COWORKING_TEMPLATES keys

        Returns:
            dict with suggested furniture list and reasoning
        """
        template = COWORKING_TEMPLATES.get(use_case)
        if not template:
            template = COWORKING_TEMPLATES["hybrid_flex"]

        room_area_sqm = self.room.area_sqm
        capacity = max(1, int(room_area_sqm / template["sqm_per_person"]))

        # Calculate available area (subtract ~20% for circulation)
        usable_area = self.room.area * 0.80  # in sq cm

        # Calculate furniture counts based on ratios and available area
        suggestions = []
        total_furniture_area = 0

        for category, ratio in template["furniture_ratios"].items():
            dims = DEFAULT_DIMENSIONS.get(category, {"width": 80, "depth": 60})
            piece_area = dims["width"] * dims["depth"] * CLEARANCE_AREA.get(category, 1.5)
            allocated_area = usable_area * ratio
            count = max(1, int(allocated_area / piece_area))

            # Clamp counts to reasonable ranges
            if category == "chair":
                # Chairs should roughly match desk + table seating
                count = min(count, capacity * 2)
            elif category in ("meeting_table", "shared_table"):
                count = min(count, max(1, capacity // 4))
            elif category == "storage":
                count = min(count, max(1, capacity // 3))

            furniture_area = count * piece_area
            total_furniture_area += furniture_area

            # Get catalog piece if available
            catalog_piece = None
            if self.catalog:
                cat_pieces = self.catalog.get_by_category(category)
                if cat_pieces:
                    catalog_piece = cat_pieces[0]

            suggestions.append({
                "category": category,
                "piece_id": catalog_piece.id if catalog_piece else None,
                "piece_name": catalog_piece.name if catalog_piece else category.replace("_", " ").title(),
                "count": count,
                "width": catalog_piece.width if catalog_piece else dims["width"],
                "depth": catalog_piece.depth if catalog_piece else dims["depth"],
                "area_allocated_pct": round(ratio * 100, 1),
            })

        utilization = total_furniture_area / self.room.area if self.room.area > 0 else 0

        return {
            "use_case": use_case,
            "label": template["label"],
            "description": template["description"],
            "room_area_sqm": round(room_area_sqm, 1),
            "estimated_capacity": capacity,
            "furniture": suggestions,
            "estimated_utilization": round(utilization * 100, 1),
            "density": template["density"],
        }

    def suggest_all(self):
        """Get suggestions for all use cases."""
        results = {}
        for key in COWORKING_TEMPLATES:
            results[key] = self.suggest_for_use_case(key)
        return results

    def analyze_room(self):
        """Analyze room characteristics and recommend best use cases."""
        area = self.room.area_sqm
        aspect = 1.0
        bounds = self.room.bounds
        w = bounds[2] - bounds[0]
        h = bounds[3] - bounds[1]
        if min(w, h) > 0:
            aspect = max(w, h) / min(w, h)

        num_windows = len(self.room.windows)
        num_doors = len(self.room.doors)

        recommendations = []

        # Small rooms (< 30 sqm) → hot desking or team pods
        if area < 30:
            recommendations.append({
                "use_case": "hot_desking",
                "fit_score": 90,
                "reason": f"Compact room ({area:.0f} sqm) is ideal for efficient hot desking layout",
            })
            recommendations.append({
                "use_case": "team_pods",
                "fit_score": 75,
                "reason": "Can fit 1-2 team pods comfortably",
            })

        # Medium rooms (30-60 sqm) → most use cases work
        elif area < 60:
            recommendations.append({
                "use_case": "hybrid_flex",
                "fit_score": 90,
                "reason": f"Medium room ({area:.0f} sqm) offers flexibility for mixed workspace",
            })
            recommendations.append({
                "use_case": "team_pods",
                "fit_score": 85,
                "reason": "Good size for 2-4 team pod clusters",
            })
            if num_windows >= 2:
                recommendations.append({
                    "use_case": "collaborative_hub",
                    "fit_score": 80,
                    "reason": "Multiple windows provide good natural light for collaboration",
                })

        # Large rooms (> 60 sqm) → collaborative hub, multi-zone
        else:
            recommendations.append({
                "use_case": "hybrid_flex",
                "fit_score": 95,
                "reason": f"Large room ({area:.0f} sqm) can support all workspace types",
            })
            recommendations.append({
                "use_case": "collaborative_hub",
                "fit_score": 90,
                "reason": "Ample space for creative collaboration zones",
            })
            recommendations.append({
                "use_case": "meeting_heavy",
                "fit_score": 80,
                "reason": "Can accommodate multiple meeting and breakout areas",
            })

        # Window bonus for lounge/collaborative
        if num_windows >= 3:
            for rec in recommendations:
                if rec["use_case"] in ("collaborative_hub", "meeting_heavy"):
                    rec["fit_score"] = min(100, rec["fit_score"] + 5)
                    rec["reason"] += " (boosted by excellent natural light)"

        recommendations.sort(key=lambda r: r["fit_score"], reverse=True)

        return {
            "room_analysis": {
                "area_sqm": round(area, 1),
                "aspect_ratio": round(aspect, 2),
                "num_walls": len(self.room.walls),
                "num_doors": num_doors,
                "num_windows": num_windows,
                "shape": "elongated" if aspect > 1.8 else "compact" if aspect < 1.3 else "regular",
            },
            "recommendations": recommendations,
        }
