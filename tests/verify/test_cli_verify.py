"""End-to-end CLI: build --store, then verify by goal hash; second call cached."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ENV = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}

SRC = """module m

goal triple {
  intent: "triples"
  in: n Int
  out: Int
  fx: pure
  verify:
    out == n * 3
}

fn triple(n Int) -> Int
  pure
{
  ret n * 3
}
"""


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sigil.cli", *args], capture_output=True, text=True, env=ENV
    )


def test_build_store_then_verify_then_cached(tmp_path) -> None:
    sg = tmp_path / "m.sg"
    sg.write_text(SRC)
    (tmp_path / "inputs.json").write_text('{"n": 4}')

    r = run_cli("build", str(sg), "--out", str(tmp_path), "--store", str(tmp_path), "--json")
    assert r.returncode == 0, r.stderr
    goal_hash = json.loads(r.stdout)["goals"]["triple"]

    r1 = run_cli(
        "verify",
        "#" + goal_hash[:8],
        "--store",
        str(tmp_path),
        "--inputs",
        str(tmp_path / "inputs.json"),
        "--json",
    )
    assert r1.returncode == 0, r1.stderr
    d1 = json.loads(r1.stdout)
    assert d1["status"] == "pass" and d1["cached"] is False
    assert d1["binding"]["impl"]

    r2 = run_cli(
        "verify",
        "#" + goal_hash[:8],
        "--store",
        str(tmp_path),
        "--inputs",
        str(tmp_path / "inputs.json"),
        "--json",
    )
    d2 = json.loads(r2.stdout)
    assert d2["status"] == "pass" and d2["cached"] is True


def test_verify_without_store_is_actionable(tmp_path) -> None:
    r = run_cli("verify", "#dead", "--store", str(tmp_path))
    assert r.returncode == 2
    assert "Remedy" in r.stderr
