"""Device-profile registry: per-brand unlock quirks, key combos, chipsets.

Data lives in profiles.json next to this module (edit the JSON to add a
brand — no code changes needed). ``info`` attaches the matching profile
automatically from the phone's reported brand/model.

Matching: case-insensitive substring match against the brand and model
strings; aliases cover sub-brands (Redmi/POCO -> Xiaomi, iQOO -> Vivo).
Unknown devices get the generic fallback profile.
"""
import json
import os

_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "profiles.json")


def _load():
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_profiles():
    """Return [(brand, chipset summary)] for every brand profile."""
    data = _load()
    return [(p["brand"], ", ".join(p.get("chipsets", [])) or "—")
            for p in data["profiles"]]


def get_profile(query):
    """Find a profile by brand, alias, or model substring.

    Returns the profile dict, or the generic fallback when nothing matches.
    """
    data = _load()
    q = (query or "").strip().lower()
    for p in data["profiles"]:
        if q == p["brand"].lower():
            return p
        if q in [a.lower() for a in p.get("aliases", [])]:
            return p
    for p in data["profiles"]:
        hay = " ".join([p["brand"]] + p.get("aliases", [])).lower()
        if q and q in hay:
            return p
    return data["generic"]


def match_device(brand="", model=""):
    """Match a connected device (brand/model strings) to a profile."""
    for query in (brand, model):
        if query:
            p = get_profile(query)
            if p["brand"] != "Generic Android":
                return p
    return get_profile("generic")


def format_profile(profile):
    """Render a profile as readable text."""
    lines = [f"{profile['brand']}"]
    if profile.get("chipsets"):
        lines.append(f"  Chipsets: {', '.join(profile['chipsets'])}")
    for key, label in (("fastboot_keys", "Fastboot"),
                       ("recovery_keys", "Recovery"),
                       ("download_keys", "Download mode"),
                       ("edl_keys", "EDL"),
                       ("brom_keys", "BROM")):
        if profile.get(key):
            lines.append(f"  {label}: {profile[key]}")
    u = profile.get("unlock", {})
    lines.append(f"  Unlock: {u.get('method', '—')}")
    if u.get("wait"):
        lines.append(f"  Wait: {u['wait']}")
    for note in u.get("notes", []):
        lines.append(f"    - {note}")
    if profile.get("frp_partition"):
        lines.append(f"  FRP partition: {profile['frp_partition']}")
    if profile.get("notes"):
        lines.append(f"  Notes: {profile['notes']}")
    return "\n".join(lines)
