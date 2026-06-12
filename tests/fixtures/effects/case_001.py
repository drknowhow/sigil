import json
from pathlib import Path

CACHE = Path("./cache")

def fetch_cached(t):
    p = CACHE / f"{t}.json"
    if p.exists():
        return json.loads(p.read_text())
    return None
