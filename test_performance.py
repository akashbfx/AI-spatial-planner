"""Quick performance test for the hybrid layout engine."""
import requests
import json
import time

url = "http://127.0.0.1:5000/api/generate-layouts"

payload = {
    "room": {
        "vertices": [[0,0],[800,0],[800,600],[0,600]],
        "doors": [{"position":[400,0],"width":90,"wall_index":0}],
        "windows": [{"position":[800,300],"width":150,"wall_index":1}]
    },
    "furniture": [
        {"category":"work_desk","width":120,"depth":60,"count":4},
        {"category":"chair","width":50,"depth":50,"count":4},
        {"category":"meeting_table","width":240,"depth":120,"count":1},
        {"category":"storage","width":80,"depth":40,"count":2},
        {"category":"lounge","width":80,"depth":80,"count":1}
    ],
    "preferences": {
        "sun_orientation": 180,
        "daylight_priority": "medium",
        "use_case": "hybrid_flex"
    }
}

print("=" * 60)
print("HYBRID ENGINE PERFORMANCE TEST")
print("=" * 60)

# Test 1: First request (cold)
t1 = time.time()
r = requests.post(url, json=payload)
client_ms_1 = round((time.time() - t1) * 1000)
d = r.json()

if r.status_code == 200 and "layouts" in d:
    print(f"\n[PASS] Status: {r.status_code}")
    print(f"Engine: {d.get('engine', '?')}")
    print(f"Server time: {d.get('_request_ms', '?')}ms")
    print(f"Client time: {client_ms_1}ms")
    print(f"Cache hit: {d.get('_cache_hit', False)}")
    
    timing = d.get("timing", {})
    if timing:
        print(f"\nTiming breakdown:")
        print(f"  Grid engine: {timing.get('grid_engine_ms', '?')}ms")
        print(f"  ML refinement: {timing.get('ml_refinement_ms', '?')}ms")
        print(f"  Scoring: {timing.get('scoring_ms', '?')}ms")
        print(f"  Total backend: {timing.get('total_ms', '?')}ms")
    
    print(f"\nLayouts generated: {len(d['layouts'])}")
    for l in d["layouts"]:
        s = l["scores"]
        print(f"  Layout {l['layout_id']}: composite={s['composite']}, grade={s['grade']}, "
              f"space={s['axes']['space_efficiency']}, usability={s['axes']['usability']}, "
              f"daylight={s['axes']['daylight_comfort']}, flow={s['axes']['movement_flow']}")
    
    # Check furniture alignment
    print(f"\nFurniture alignment check:")
    desks = [p for p in d["layouts"][0]["placements"] if p["category"] == "work_desk"]
    if desks:
        rotations = [p["rotation"] for p in desks]
        uniform = len(set(rotations)) == 1
        print(f"  Desk rotations: {rotations}")
        print(f"  All uniform: {'YES' if uniform else 'NO (mixed)'}")
    
    chairs = [p for p in d["layouts"][0]["placements"] if p["category"] == "chair"]
    if chairs:
        print(f"  Chair rotations: {[p['rotation'] for p in chairs]}")
    
    # Check grid snapping
    all_positions = [(p["x"], p["y"]) for p in d["layouts"][0]["placements"]]
    grid_aligned = all(x % 10 == 0 and y % 10 == 0 for x, y in all_positions)
    print(f"  All grid-snapped (10cm): {'YES' if grid_aligned else 'NO'}")
    
else:
    print(f"\n[FAIL] Status: {r.status_code}")
    print(f"Error: {d.get('error', 'Unknown')}")

# Test 2: Cache hit
print("\n" + "-" * 40)
print("CACHE TEST (identical request):")
t2 = time.time()
r2 = requests.post(url, json=payload)
client_ms_2 = round((time.time() - t2) * 1000)
d2 = r2.json()
print(f"  Client time: {client_ms_2}ms")
print(f"  Cache hit: {d2.get('_cache_hit', False)}")
print(f"  Server time: {d2.get('_request_ms', '?')}ms")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
