from pathlib import Path

def slurp(name):
    return Path(name).open().read()
