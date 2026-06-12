"""Phase 2 exit gate (plan section 4): examples/new-module transpiles, runs,
and a deliberately over-budget effect is rejected with an actionable error."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
EXAMPLE = ROOT / "examples" / "new-module"
ENV = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}


def test_demo_runs_end_to_end(tmp_path) -> None:
    r = subprocess.run(
        [sys.executable, str(EXAMPLE / "run_demo.py")], capture_output=True, text=True, env=ENV
    )
    assert r.returncode == 0, r.stderr + r.stdout
    assert "verify: all clauses passed" in r.stdout
    assert "rejected as expected" in r.stdout


def test_cli_build_writes_files(tmp_path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "sigil.cli",
            "build",
            str(EXAMPLE / "prices.sg"),
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=ENV,
    )
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "prices.py").exists()
    assert (tmp_path / "test_fetch_prices.py").exists()


def test_cli_build_rejects_over_budget(tmp_path) -> None:
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "sigil.cli",
            "build",
            str(EXAMPLE / "over_budget.sg"),
            "--out",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        env=ENV,
    )
    assert r.returncode == 2
    assert "fetch_prices -> save_cache: open requires !fs" in r.stderr
    assert "Remedy" in r.stderr
