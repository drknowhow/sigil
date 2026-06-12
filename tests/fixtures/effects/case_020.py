from pathlib import Path

def read_config(p: Path):
    return p.read_text()
