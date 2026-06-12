"""Plan section 10 checklist items that are testable (sigil-quality-gates)."""

import json
import subprocess
import sys
from pathlib import Path

from sigil.core.ast import Law
from sigil.store.repo import Store

ROOT = Path(__file__).parent.parent.parent
ENV = {"PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "sigil.cli", *args], capture_output=True, text=True, env=ENV
    )


def test_no_raw_traceback_reaches_users() -> None:
    bad_calls = [
        ("lift", "no_such_path.py"),
        ("build", "no_such.sg"),
        ("verify", "#dead", "--store", "/nonexistent-dir"),
        ("lift",),  # missing required arg -> argparse error, not traceback
    ]
    for args in bad_calls:
        r = run_cli(*args)
        assert r.returncode != 0
        assert "Traceback" not in r.stderr + r.stdout, args


def test_help_complete_for_every_command() -> None:
    for cmd in ([], ["lift"], ["build"], ["verify"], ["serve"]):
        r = run_cli(*cmd, "--help")
        assert r.returncode == 0
        assert "usage" in r.stdout.lower()


def test_json_flag_on_data_commands(tmp_path) -> None:
    sg = tmp_path / "m.sg"
    sg.write_text("module m\n\nfn id(x Int) -> Int\n  pure\n{\n  ret x\n}\n")
    r = run_cli("build", str(sg), "--out", str(tmp_path), "--json")
    json.loads(r.stdout)
    r = run_cli("lift", str(ROOT / "seed" / "demo_module.py"), "--json")
    json.loads(r.stdout)


def test_store_contains_no_absolute_paths(tmp_path) -> None:
    store = Store.create(tmp_path)
    store.put(Law(text="x"))
    store.register_goal("a" * 64, "b" * 64, "g")
    blob = ""
    for f in (tmp_path / ".sigil").rglob("*"):
        if f.is_file():
            blob += f.read_text(errors="replace")
    assert str(tmp_path) not in blob  # relocatable: no absolute paths persisted


def test_version_flag() -> None:
    r = run_cli("--version")
    assert r.returncode == 0 and "sigil" in r.stdout
