"""v1.2 gates: sigil check (CI regression gate) + sigil watch (poll engine)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
ENV = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}

GOOD = """module m

goal triple {
  intent: "triples"
  in: n Int
  out: Int
  fx: pure
  inputs: "triple.inputs.json"
  verify:
    out == n * 3
}

fn triple(n Int) -> Int
  pure
{
  ret n * 3
}
"""
BAD = GOOD.replace("ret n * 3", "ret n * 2")


def run_cli(*args: str, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sigil.cli", *args], capture_output=True, text=True, env=ENV, cwd=cwd
    )


def _project(d: Path, src: str) -> None:
    (d / "m.sg").write_text(src)
    (d / "triple.inputs.json").write_text('{"n": 6}')


def test_check_passes_then_fails_on_regression(tmp_path) -> None:
    _project(tmp_path, GOOD)
    r = run_cli("check", str(tmp_path), cwd=tmp_path)
    assert r.returncode == 0, r.stderr + r.stdout
    assert "triple" in r.stdout and "pass" in r.stdout

    _project(tmp_path, BAD)
    r2 = run_cli("check", str(tmp_path), cwd=tmp_path)
    assert r2.returncode == 1
    assert "fail" in r2.stdout


def test_check_against_detects_dropped_contract(tmp_path) -> None:
    _project(tmp_path, GOOD)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
    for cmd in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run([*git, *cmd], cwd=tmp_path, capture_output=True, env=ENV)
    (tmp_path / "m.sg").write_text("module m\n\nfn f(x Int) -> Int\n  pure\n{\n  ret x\n}\n")
    r = run_cli("check", str(tmp_path), "--against", "HEAD", cwd=tmp_path)
    assert r.returncode == 1
    assert "dropped" in r.stdout and "triple" in r.stdout


def test_watch_engine_detects_and_verifies(tmp_path) -> None:
    from sigil.harness.watch import WatchState

    _project(tmp_path, BAD)
    w = WatchState([str(tmp_path)], store_dir=tmp_path)
    assert w.poll() == []  # baseline snapshot, no events
    (tmp_path / "m.sg").write_text(GOOD)
    events = w.poll()
    assert any("triple" in e and "pass" in e for e in events), events
    assert w.poll() == []  # quiescent again
