"""CLI: sigil lift with text + --json output; errors state cause + remedy."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DEMO = ROOT / "seed" / "demo_module.py"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sigil.cli", *args],
        capture_output=True,
        text=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"},
    )


def test_lift_text_sheet() -> None:
    r = run_cli("lift", str(DEMO))
    assert r.returncode == 0, r.stderr
    assert "fetch_prices" in r.stdout
    assert "#" in r.stdout
    assert "?" in r.stdout  # uncertainty markers survive to display


def test_lift_json() -> None:
    r = run_cli("lift", str(DEMO), "--json")
    assert r.returncode == 0, r.stderr
    doc = json.loads(r.stdout)
    names = [e["name"] for f in doc["files"] for e in f["entries"]]
    assert "fetch_prices" in names
    fx = {e["name"]: e["effects"] for f in doc["files"] for e in f["entries"]}
    assert any("fs" in x for x in fx["fetch_prices"])


def test_missing_path_error_is_actionable() -> None:
    r = run_cli("lift", "no_such_file.py")
    assert r.returncode != 0
    msg = (r.stderr + r.stdout).lower()
    assert "remedy" in msg
