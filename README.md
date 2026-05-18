# 🏢 Spatial Planner

https://ai-spatial-planner-akashb.vercel.app/

AI-integrated software prototype developed as part of the architectural thesis project: K-SPACE: Aerospace Innovation Hub, Thiruvananthapuram, Kerala. at NIT Calicut, Semester X

An AI-powered coworking space layout generator. You describe your room and what furniture you need — it automatically generates multiple optimised layout options in under 500ms, with daylight analysis, an interactive canvas, and a natural language chat assistant. for office spaces

This software is part of an academic architectural thesis focused on designing a next-generation aerospace innovation campus integrating architecture, technology, and intelligent systems.
---

## ✨ What it does

- **Generates room layouts automatically** — give it your room dimensions and furniture list, it figures out where everything goes
- **Multiple layout variants** — produces 4 different layout options per request so you can compare
- **Daylight-aware placement** — knows where the sun comes from and places work desks near windows accordingly
- **Interactive canvas** — drag, rotate, and customise furniture positions after generation
- **Isometric 3D view** — switch from flat floor plan to a 3D bird's eye perspective
- **AI chat assistant** — type things like "I need seating for 12 people" or "make it more collaborative" and it adjusts the configuration
- **Smart suggestions** — picks furniture automatically based on your use case (hot desking, team pods, meeting-heavy, etc.)
- **Custom furniture** — create your own furniture pieces with custom dimensions
- **Export to SVG** — download your final layout as a vector file

---

## 🏗️ How it's built

### Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3, Flask |
| Layout Engine | NumPy, SciPy, Shapely |
| Frontend | Vanilla JavaScript, HTML5 Canvas |
| SVG Export | svgwrite |
| Production Server | Gunicorn |

### Project structure

```
spatial-planner/
│
├── app.py                  # Flask app — all API routes
├── config.py               # Settings (engine toggles, cache size, GA params)
├── requirements.txt        # Python dependencies
├── Procfile                # For deployment (tells server how to start)
│
├── engine/                 # All the Python brain
│   ├── optimizer.py        # Hybrid optimizer + Genetic Algorithm fallback
│   ├── grid_layout_engine.py   # Phase 1: fast deterministic grid placement
│   ├── ml_refinement.py    # Phase 2: ML-style iterative refinement
│   ├── scoring.py          # Scores layouts on 4 axes
│   ├── constraints.py      # Rules — clearances, door access, wall proximity
│   ├── daylight.py         # Sun orientation and window light analysis
│   ├── geometry.py         # Room shape, doors, windows (uses Shapely polygons)
│   ├── furniture.py        # Furniture pieces and catalog loader
│   ├── layout_rules.py     # Architectural rules (Neufert standards)
│   ├── layout_cache.py     # LRU cache so identical requests are instant
│   ├── smart_suggest.py    # Auto-picks furniture for use cases
│   └── chat_engine.py      # Natural language → room config parser
│
├── static/
│   ├── css/style.css       # All styling
│   └── js/
│       ├── app.js          # Main controller — connects everything
│       ├── canvas.js       # Interactive floor plan canvas (HTML5 Canvas)
│       ├── isometric-view.js   # 3D isometric renderer
│       ├── chat.js         # Chat UI
│       ├── config-panel.js # Room setup panel
│       ├── layout-viewer.js    # Layout comparison viewer
│       ├── furniture-creator.js    # Custom furniture UI
│       ├── furniture-symbols.js    # SVG symbols per furniture type
│       ├── export.js       # SVG export
│       └── utils.js        # Shared helpers
│
├── templates/
│   └── index.html          # The single HTML page (Flask serves this)
│
└── data/
    ├── furniture_catalog.json  # All furniture types with dimensions
    └── room_presets.json       # Pre-built room configurations
```

---

## 🧠 How the layout engine works

This is the core of the app. When you click "Generate Layouts", here is what happens step by step:

### Step 1 — Parse the room

Your room dimensions, door positions, and window positions are converted into a **Shapely polygon** — a precise geometric shape the engine can do spatial calculations on.

```
Room input → RoomGeometry → Shapely Polygon + Door/Window objects
```

### Step 2 — Parse furniture

Each furniture item from your list is turned into a `FurniturePiece` object with its width, depth, height, and required clearance zones (the space you need to walk around it). These come from `data/furniture_catalog.json`.

### Step 3 — Daylight analysis

`DaylightAnalyzer` takes the sun orientation you set (compass bearing, e.g. 180° = south-facing sun) and calculates which zones of the room get the most natural light. It does this by:

1. Looking at each window's angle relative to the sun direction
2. Casting a "light cone" inward from each window
3. Scoring every zone of the room — **bright**, **moderate**, or **dim**

This map is used in Step 4 to prefer placing work desks in bright zones.

### Step 4 — Hybrid optimizer (primary, <500ms)

The main engine runs a two-phase pipeline:

**Phase 1 — Grid layout (~50ms)**
`GridLayoutEngine` divides the room into a grid and places furniture using deterministic rules:
- Desks go near windows (bright zones)
- Storage goes against walls
- Meeting tables go in the centre
- Minimum clearances are respected (door swing, walkway width)
- 4 different arrangement strategies are tried (e.g. perimeter-first, cluster, spine)

**Phase 2 — ML refinement (~100–200ms)**
`MLRefinementEngine` takes each grid layout and improves it iteratively:
- Small positional nudges are tried (move this piece 10cm, rotate 90°)
- Each nudge is scored — if the score improves, the nudge is kept
- Runs 3 passes per layout
- A GAN-style variation step adds diversity between the 4 variants

### Step 5 — Scoring

Every layout is scored on 4 axes (each 0–100):

| Axis | What it measures |
|---|---|
| **Space efficiency** | How well the room area is used (ideal: 35–55% occupied) |
| **Usability** | Clearances, no overlaps, door access unblocked |
| **Daylight comfort** | Are work desks in bright zones? Lounge in moderate? |
| **Movement flow** | Are the walkways clear? Can you reach every desk? |

Final score = weighted average of all 4. The best-scoring layout is shown first.

### Step 6 — Genetic Algorithm fallback (quality mode, ~5s)

If you select "Quality mode" in settings, the faster hybrid engine is skipped and a **Genetic Algorithm** runs instead:

1. 20 random layouts are generated (the "population")
2. The best ones are selected (tournament selection)
3. They're combined and mutated to create a new generation
4. This repeats for 30 generations (or until no improvement for 8 consecutive generations)
5. The top 4 survivors are returned

This produces slightly better layouts but takes 5–10× longer, which is why the hybrid engine is the default.

### Step 7 — Caching

Results are stored in an **LRU cache** (last-recently-used, max 50 entries). If you send the same room + furniture combination again, the cached result is returned instantly without re-running the engine.

---

## 💬 How the chat assistant works

`ChatEngine` is a **rule-based NLP parser** — not an external AI API. It uses regex patterns to understand what you're saying and converts it to room/furniture configuration changes.

Examples of what it understands:

| You type | What happens |
|---|---|
| `"I need seating for 12 people"` | Calculates furniture count for 12 people |
| `"Add 3 standing desks"` | Adds 3 standing desks to the furniture list |
| `"Make it more collaborative"` | Switches use case to `collaborative` mode |
| `"Desks near the window"` | Sets daylight priority to `high` |
| `"5m x 8m room"` | Updates room dimensions |

The engine matches your message against ~30 regex patterns across 8 categories (seating, furniture, room size, layout style, daylight preference, etc.).

---

## 💡 Smart Suggest

`SmartSuggestEngine` auto-fills the furniture list based on your chosen use case and room size. It knows the recommended floor area per person for each mode:

| Use case | sqm per person | Character |
|---|---|---|
| Hot Desking | 4.5 m² | Dense individual workstations |
| Team Pods | 5.5 m² | Cluster of 4–6 desks with shared tables |
| Meeting Heavy | 6.0 m² | Lots of meeting tables and breakout |
| Creative Studio | 6.5 m² | Large tables, project displays |
| Hybrid Flex | 5.0 m² | Mix of all the above |

---

## 🌐 API reference

The backend exposes these REST endpoints:

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/` | Serves the frontend HTML |
| `GET` | `/api/furniture-catalog` | All available furniture with dimensions |
| `GET` | `/api/room-presets` | Pre-built room configurations |
| `GET` | `/api/categories` | Furniture category metadata |
| `GET` | `/api/coworking-templates` | Use case templates |
| `GET` | `/api/cache-stats` | Debug: cache hit rate |
| `POST` | `/api/generate-layouts` | **Main endpoint** — runs the layout engine |
| `POST` | `/api/smart-suggest` | Auto-suggest furniture for a use case |
| `POST` | `/api/chat` | Send a message to the chat assistant |
| `POST` | `/api/analyze-daylight` | Get daylight zones for a room |
| `POST` | `/api/export-svg` | Export a layout as SVG |
| `POST` | `/api/furniture/custom` | Add a custom furniture piece |

### Example: generate layouts

```json
POST /api/generate-layouts
{
  "room": {
    "width": 800,
    "height": 600,
    "doors": [{ "position": [400, 0], "width": 90 }],
    "windows": [{ "position": [0, 300], "width": 150 }]
  },
  "furniture": [
    { "piece_id": "work_desk_standard", "count": 6 },
    { "piece_id": "chair_task", "count": 6 }
  ],
  "preferences": {
    "sun_orientation": 180,
    "daylight_priority": "high",
    "use_case": "hot_desking",
    "engine_mode": "hybrid"
  }
}
```

Response includes 4 layout variants, each with furniture placements (x, y, rotation), scores, and daylight zones.

---

## 🚀 Running locally

**Prerequisites:** Python 3.10+

```bash
# 1. Clone the repo
git clone https://github.com/your-username/spatial-planner.git
cd spatial-planner

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py

# 4. Open in browser
# http://localhost:5000
```

---

## ☁️ Deployment

The app is deployed on **Render** (free tier).

It uses **Gunicorn** as the production server (not Flask's built-in dev server). Render automatically redeploys whenever new code is pushed to the `main` branch on GitHub.

```
GitHub push → Render detects change → pip install → gunicorn app:app → live
```

---

## 📐 Architectural standards

Clearance values in the engine are based on **Neufert Architects' Data** — the standard reference for architectural space planning:

- Desk front clearance: 100cm (space to pull out a chair and stand)
- Walkway minimum: 90cm
- Door swing clearance: full arc of door width
- Meeting table: 80cm per seat

---

## 🛠️ Configuration

All engine behaviour is controlled in `config.py`:

```python
HYBRID_ENGINE_ENABLED = True       # Use fast hybrid engine (vs GA only)
ML_REFINEMENT_ITERATIONS = 3       # Refinement passes per layout
NUM_LAYOUT_VARIANTS = 4            # How many layouts to return
LAYOUT_CACHE_ENABLED = True        # Cache repeated requests
LAYOUT_CACHE_SIZE = 50             # Max LRU cache entries
GA_GENERATIONS = 30                # GA fallback generations
GA_TIME_LIMIT = 5                  # GA hard time limit (seconds)
```

---

## 📄 License
Akash B 
National Institute of Technology Calicut  
MIT — free to use, modify, and deploy.
