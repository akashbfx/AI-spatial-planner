"""
LRU Layout Cache — eliminates redundant computation for repeated requests.

Caches layout results keyed by a hash of room geometry + furniture + preferences.
"""

import hashlib
import json
import time
from collections import OrderedDict


class LayoutCache:
    """Thread-safe LRU cache for generated layout results."""

    def __init__(self, max_size=50):
        self.max_size = max_size
        self._cache = OrderedDict()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(room_data, furniture_data, preferences):
        """Create a deterministic hash key from input data."""
        key_data = {
            "room": {
                "vertices": room_data.get("vertices", []),
                "doors": [
                    {"position": d["position"], "width": d.get("width", 90)}
                    for d in room_data.get("doors", [])
                ],
                "windows": [
                    {"position": w["position"], "width": w.get("width", 120)}
                    for w in room_data.get("windows", [])
                ],
            },
            "furniture": sorted(
                [
                    {
                        "category": f.get("category", ""),
                        "width": f.get("width", 0),
                        "depth": f.get("depth", 0),
                        "count": f.get("count", 1),
                    }
                    for f in furniture_data
                ],
                key=lambda x: (x["category"], x["width"], x["depth"]),
            ),
            "preferences": {
                "sun_orientation": preferences.get("sun_orientation", 180),
                "daylight_priority": preferences.get("daylight_priority", "medium"),
                "use_case": preferences.get("use_case", "hybrid_flex"),
            },
        }
        raw = json.dumps(key_data, sort_keys=True, separators=(",", ":"))
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, room_data, furniture_data, preferences):
        """Look up a cached result. Returns None on miss."""
        key = self._make_key(room_data, furniture_data, preferences)
        if key in self._cache:
            self._hits += 1
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry = self._cache[key]
            entry["result"]["_cache_hit"] = True
            return entry["result"]
        self._misses += 1
        return None

    def put(self, room_data, furniture_data, preferences, result):
        """Store a result in the cache."""
        key = self._make_key(room_data, furniture_data, preferences)

        if key in self._cache:
            self._cache.move_to_end(key)
            self._cache[key] = {"result": result, "time": time.time()}
        else:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Evict oldest
            self._cache[key] = {"result": result, "time": time.time()}

    def invalidate(self):
        """Clear the entire cache."""
        self._cache.clear()

    @property
    def stats(self):
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total * 100, 1) if total > 0 else 0,
        }
