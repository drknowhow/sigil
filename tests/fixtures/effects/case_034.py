import json
from pathlib import Path

CFG = Path("./config.json")

def load_config():
    if CFG.exists():
        return json.loads(CFG.read_text())
    return {}
