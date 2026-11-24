#!/usr/bin/env python3
"""Regenerate android/app/src/main/assets/frp-catalog.json from
openunlock/frp.py (the single source of truth for the FRP catalog).
Run from the repo root:  python3 android/manual/generate-frp-catalog.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from openunlock import frp  # noqa: E402

catalog = {
    "official_path": frp.official_path(),
    "methods": [
        {"id": mid, "name": m["name"], "description": m.get("description", ""),
         "applies_to": m.get("applies_to", ""), "status": m.get("status", ""),
         "patched_as_of": m.get("patched_as_of", ""), "steps": m.get("steps", [])}
        for mid, m in frp.METHODS.items()
    ],
}
out = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main",
                   "assets", "frp-catalog.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w") as f:
    json.dump(catalog, f, indent=1)
print(f"Wrote {out}: {len(catalog['methods'])} methods")
