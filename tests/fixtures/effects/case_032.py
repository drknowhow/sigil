from pathlib import Path

BASE = Path("./cache")

def cache_path(name):
    return BASE / f"{name}.json"

def read_cache(name):
    p = cache_path(name)
    if p.exists():
        return p.read_text()
    return None
