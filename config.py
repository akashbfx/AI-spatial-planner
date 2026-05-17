"""Application configuration."""

class Config:
    SECRET_KEY = "spatial-planner-dev-key"
    DEBUG = True

    # ── Hybrid Engine (Primary — fast rule-based + ML refinement) ──
    HYBRID_ENGINE_ENABLED = True
    ML_REFINEMENT_ENABLED = True
    ML_REFINEMENT_ITERATIONS = 3        # Max refinement passes per layout
    ML_GAN_SIMULATION_ENABLED = True    # Simulated Pix2Pix variation
    NUM_LAYOUT_VARIANTS = 4             # Number of distinct layouts to return

    # ── Layout Cache ──
    LAYOUT_CACHE_ENABLED = True
    LAYOUT_CACHE_SIZE = 50              # LRU cache entries

    # ── Genetic Algorithm (Fallback only — drastically reduced) ──
    GA_POPULATION_SIZE = 20
    GA_GENERATIONS = 30
    GA_MUTATION_RATE = 0.15
    GA_CROSSOVER_RATE = 0.7
    GA_TOURNAMENT_SIZE = 3
    GA_ELITE_COUNT = 3
    GA_EARLY_STOP_GENERATIONS = 8       # Stop if no improvement for N generations
    GA_NUM_LAYOUTS = 4                  # Number of distinct layouts to return
    GA_TIME_LIMIT = 5                   # Seconds (down from 30)

    # Neufert Architectural Standards (in cm)
    DOOR_CLEARANCE = 100
    PRIMARY_CORRIDOR_WIDTH = 120
    SECONDARY_CORRIDOR_WIDTH = 90
    WHEELCHAIR_TURNING_RADIUS = 150
    WORKSTATION_SPACING = 140
    DESK_WALL_GAP = 5
    MEETING_TABLE_CHAIR_CLEARANCE = 80
    MIN_PASSAGE_WIDTH = 75

    # Daylight zones (in cm from window)
    DAYLIGHT_PRIMARY_ZONE = 200
    DAYLIGHT_SECONDARY_ZONE = 400
    DAYLIGHT_AMBIENT_ZONE = 600

    # Scoring weights
    SCORE_WEIGHT_SPACE_EFFICIENCY = 0.25
    SCORE_WEIGHT_USABILITY = 0.25
    SCORE_WEIGHT_DAYLIGHT = 0.25
    SCORE_WEIGHT_MOVEMENT_FLOW = 0.25

    # Grid snap (cm)
    GRID_SNAP = 10
    ROTATION_SNAP = 90  # degrees
