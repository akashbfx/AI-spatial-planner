"""
Flask application — API endpoints for the spatial planner.

Uses hybrid rule-based + ML optimizer (primary) with GA fallback.
"""

import os
import json
import io
import time
from flask import Flask, render_template, request, jsonify, send_file

from config import Config
from engine.geometry import RoomGeometry, Door, Window
from engine.furniture import FurniturePiece, FurnitureCatalog, CATEGORY_PROPERTIES
from engine.constraints import ConstraintChecker
from engine.optimizer import HybridLayoutOptimizer, GeneticLayoutOptimizer
from engine.daylight import DaylightAnalyzer
from engine.scoring import LayoutScorer
from engine.smart_suggest import SmartSuggestEngine, COWORKING_TEMPLATES
from engine.chat_engine import ChatEngine
from engine.layout_cache import LayoutCache

app = Flask(__name__)
app.config.from_object(Config)

# Load data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

catalog = FurnitureCatalog(os.path.join(DATA_DIR, "furniture_catalog.json"))
chat_engine = ChatEngine(catalog)

with open(os.path.join(DATA_DIR, "room_presets.json"), "r") as f:
    room_presets = json.load(f)

# Layout cache (singleton)
layout_cache = LayoutCache(max_size=app.config.get("LAYOUT_CACHE_SIZE", 50))


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/furniture-catalog")
def get_catalog():
    response = jsonify(catalog.to_dict())
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/api/room-presets")
def get_presets():
    response = jsonify(room_presets)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/api/categories")
def get_categories():
    response = jsonify({
        "categories": {k: v for k, v in CATEGORY_PROPERTIES.items()},
    })
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/api/furniture/custom", methods=["POST"])
def add_custom_furniture():
    data = request.json
    piece = catalog.add_custom(
        name=data.get("name", "Custom Piece"),
        category=data.get("category", "work_desk"),
        width=data.get("width", 100),
        depth=data.get("depth", 60),
        height=data.get("height", 75),
        clearance_front=data.get("clearance_front"),
        clearance_sides=data.get("clearance_sides"),
        clearance_back=data.get("clearance_back"),
    )
    return jsonify({"success": True, "piece": piece.to_dict()})


@app.route("/api/generate-layouts", methods=["POST"])
def generate_layouts():
    try:
        request_start = time.time()
        data = request.json

        # Parse room geometry
        room = RoomGeometry.from_dict(data.get("room", {}))
        if room.polygon.is_empty:
            return jsonify({"error": "Invalid room geometry"}), 400

        # Parse furniture list
        furniture_items = data.get("furniture", [])
        if not furniture_items:
            return jsonify({"error": "No furniture specified"}), 400

        # Parse preferences
        prefs = data.get("preferences", {})
        sun_orientation = prefs.get("sun_orientation", 180)
        daylight_priority = prefs.get("daylight_priority", "medium")
        use_case = prefs.get("use_case", "hybrid_flex")
        engine_mode = prefs.get("engine_mode", "hybrid")  # "hybrid" or "quality"

        # Check cache first
        if app.config.get("LAYOUT_CACHE_ENABLED", True):
            cached = layout_cache.get(
                data.get("room", {}), furniture_items, prefs
            )
            if cached:
                cached["_cache_hit"] = True
                cached["_request_ms"] = round((time.time() - request_start) * 1000, 1)
                return jsonify(cached)

        # Build furniture pieces
        pieces = []
        for item in furniture_items:
            piece_id = item.get("piece_id")
            count = item.get("count", 1)

            if piece_id and catalog.get_piece(piece_id):
                template = catalog.get_piece(piece_id)
                for c in range(count):
                    pieces.append(FurniturePiece(
                        id=f"{template.id}_{c}",
                        name=template.name,
                        category=template.category,
                        width=item.get("width", template.width),
                        depth=item.get("depth", template.depth),
                        height=template.height,
                    ))
            else:
                cat = item.get("category", "work_desk")
                for c in range(count):
                    pieces.append(FurniturePiece(
                        id=f"{cat}_{c}",
                        name=item.get("name", cat.replace("_", " ").title()),
                        category=cat,
                        width=item.get("width", 120),
                        depth=item.get("depth", 60),
                        height=item.get("height", 75),
                    ))

        if not pieces:
            return jsonify({"error": "No valid furniture pieces"}), 400

        # Create daylight analyzer
        daylight = DaylightAnalyzer(room, sun_orientation, daylight_priority)

        # Choose engine
        use_hybrid = (
            app.config.get("HYBRID_ENGINE_ENABLED", True)
            and engine_mode != "quality"
        )

        if use_hybrid:
            # ── Hybrid Engine (fast, <500ms) ──
            optimizer = HybridLayoutOptimizer(
                room_geometry=room,
                furniture_pieces=pieces,
                daylight_analyzer=daylight,
                num_layouts=app.config.get("NUM_LAYOUT_VARIANTS", 4),
                use_case=use_case,
                ml_iterations=app.config.get("ML_REFINEMENT_ITERATIONS", 3),
                gan_enabled=app.config.get("ML_GAN_SIMULATION_ENABLED", True),
            )
            result = optimizer.optimize()
        else:
            # ── GA Fallback (slower, ~5s) ──
            optimizer = GeneticLayoutOptimizer(
                room_geometry=room,
                furniture_pieces=pieces,
                daylight_analyzer=daylight,
                population_size=app.config.get("GA_POPULATION_SIZE", 20),
                generations=app.config.get("GA_GENERATIONS", 30),
                mutation_rate=app.config.get("GA_MUTATION_RATE", 0.15),
                crossover_rate=app.config.get("GA_CROSSOVER_RATE", 0.7),
                elite_count=app.config.get("GA_ELITE_COUNT", 3),
                num_layouts=app.config.get("GA_NUM_LAYOUTS", 4),
                use_case=use_case,
            )
            result = optimizer.optimize(
                time_limit=app.config.get("GA_TIME_LIMIT", 5)
            )

        # Add room info to response
        result["room"] = room.to_dict()
        result["daylight_zones"] = []
        for z in daylight.daylight_zones:
            poly_coords = list(z["polygon"].exterior.coords) if hasattr(z["polygon"], 'exterior') else []
            result["daylight_zones"].append({
                "zone_type": z["zone_type"],
                "quality": z["quality"],
                "quality_score": z["quality_score"],
                "polygon": [[round(c[0], 1), round(c[1], 1)] for c in poly_coords],
            })

        # Add request timing
        result["_request_ms"] = round((time.time() - request_start) * 1000, 1)
        result["_cache_hit"] = False

        # Cache result
        if app.config.get("LAYOUT_CACHE_ENABLED", True):
            layout_cache.put(
                data.get("room", {}), furniture_items, prefs, result
            )

        return jsonify(result)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/smart-suggest", methods=["POST"])
def smart_suggest():
    try:
        data = request.json
        room = RoomGeometry.from_dict(data.get("room", {}))
        use_case = data.get("use_case", "hybrid_flex")

        engine = SmartSuggestEngine(room, catalog)

        if use_case == "analyze":
            result = engine.analyze_room()
            result["all_suggestions"] = engine.suggest_all()
            return jsonify(result)
        else:
            result = engine.suggest_for_use_case(use_case)
            return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        data = request.json
        message = data.get("message", "")
        response = chat_engine.process_message(message)
        return jsonify(response)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analyze-daylight", methods=["POST"])
def analyze_daylight():
    try:
        data = request.json
        room = RoomGeometry.from_dict(data.get("room", {}))
        sun_orientation = data.get("sun_orientation", 180)

        analyzer = DaylightAnalyzer(room, sun_orientation)
        daylight_map = analyzer.get_daylight_map()

        zones = []
        for z in analyzer.daylight_zones:
            poly_coords = list(z["polygon"].exterior.coords) if hasattr(z["polygon"], 'exterior') else []
            zones.append({
                "zone_type": z["zone_type"],
                "quality": z["quality"],
                "quality_score": z["quality_score"],
                "polygon": [[round(c[0], 1), round(c[1], 1)] for c in poly_coords],
            })

        return jsonify({
            "zones": zones,
            "daylight_map": daylight_map,
            "sun_orientation": sun_orientation,
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/export-svg", methods=["POST"])
def export_svg():
    try:
        import svgwrite
        data = request.json
        layout = data.get("layout", {})
        room_data = data.get("room", {})
        room = RoomGeometry.from_dict(room_data)

        # Create SVG
        bounds = room.bounds
        margin = 50
        w = bounds[2] - bounds[0] + margin * 2
        h = bounds[3] - bounds[1] + margin * 2
        scale = min(800 / w, 600 / h) if w > 0 and h > 0 else 1

        dwg = svgwrite.Drawing(size=(f"{w * scale}px", f"{h * scale}px"))
        dwg.viewbox(bounds[0] - margin, bounds[1] - margin, w, h)

        # Background
        dwg.add(dwg.rect(
            insert=(bounds[0] - margin, bounds[1] - margin),
            size=(w, h),
            fill="#1a1a2e"
        ))

        # Room polygon
        vertices = [(v[0], v[1]) for v in room.vertices]
        if vertices:
            dwg.add(dwg.polygon(vertices, fill="#252540", stroke="#4A90D9", stroke_width=3))

        # Doors
        for door in room.doors:
            x, y = door.position
            dwg.add(dwg.circle(center=(x, y), r=door.width / 2,
                             fill="none", stroke="#4FC3F7", stroke_width=2))

        # Windows
        for window in room.windows:
            x, y = window.position
            dwg.add(dwg.line(
                start=(x - window.width / 2, y),
                end=(x + window.width / 2, y),
                stroke="#FFD54F", stroke_width=4
            ))

        # Furniture
        for item in layout.get("placements", []):
            x, y = item["x"], item["y"]
            fw, fd = item["width"], item["depth"]
            color = item.get("color", "#888")
            rot = item.get("rotation", 0)

            g = dwg.g(transform=f"translate({x},{y}) rotate({rot})")
            g.add(dwg.rect(
                insert=(-fw / 2, -fd / 2), size=(fw, fd),
                fill=color, fill_opacity=0.7,
                stroke=color, stroke_width=1, rx=3, ry=3
            ))
            g.add(dwg.text(
                item.get("name", "")[:10],
                insert=(0, 4),
                text_anchor="middle",
                font_size="8", fill="white", font_family="sans-serif"
            ))
            dwg.add(g)

        # Grid
        for gx in range(int(bounds[0]), int(bounds[2]), 100):
            dwg.add(dwg.line(
                start=(gx, bounds[1]), end=(gx, bounds[3]),
                stroke="#ffffff", stroke_opacity=0.05, stroke_width=0.5
            ))
        for gy in range(int(bounds[1]), int(bounds[3]), 100):
            dwg.add(dwg.line(
                start=(bounds[0], gy), end=(bounds[2], gy),
                stroke="#ffffff", stroke_opacity=0.05, stroke_width=0.5
            ))

        svg_string = dwg.tostring()

        return app.response_class(
            response=svg_string,
            status=200,
            mimetype="image/svg+xml",
            headers={"Content-Disposition": "attachment;filename=layout.svg"}
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/coworking-templates")
def get_coworking_templates():
    response = jsonify({"templates": COWORKING_TEMPLATES})
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/api/cache-stats")
def cache_stats():
    """Debug endpoint for cache statistics."""
    return jsonify(layout_cache.stats)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
