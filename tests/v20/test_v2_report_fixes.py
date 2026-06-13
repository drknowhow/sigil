"""v2.0.1 — fixes from firstuse/V2_REPORT.md (Windows/encoding + invariant persistence)."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


# ---- Bug 2: encoding ------------------------------------------------------


def test_sheet_footer_is_ascii_only() -> None:
    # machine-facing output must survive a cp1252 console (no ≈ · × — glyphs)
    from sigil.lift.python import lift_source, render_sheet

    src = (ROOT / "seed" / "demo_module.py").read_text()
    sheet = render_sheet(lift_source(src, name="demo_module"))
    sheet.encode("cp1252")  # raises if any glyph is non-cp1252
    assert sheet.isascii()


def test_cli_lift_survives_cp1252_stdout() -> None:
    # simulate a Windows console: force a legacy stdio encoding for the child
    import os

    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "cp1252",
    }
    env.pop("PYTHONUTF8", None)
    r = subprocess.run(
        [sys.executable, "-m", "sigil.cli", "lift", str(ROOT / "seed" / "demo_module.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "fetch_prices" in r.stdout
    assert "UnicodeEncodeError" not in r.stderr and "charmap" not in r.stderr


def test_runner_subprocess_pins_utf8_encoding() -> None:
    import inspect

    from sigil.verify import runner

    src = inspect.getsource(runner)
    # every capture_output subprocess.run must declare encoding (no locale codec)
    assert src.count("capture_output=True") == src.count('encoding="utf-8"')


# ---- Bug 1: invariant persistence -----------------------------------------

SG = """module codec

invariant round_trip {
  in: x Int
  over: enc, dec
  verify:
    dec(enc(x)) == x
}

fn enc(x Int) -> Int
  pure
{
  ret x + 1
}

fn dec(y Int) -> Int
  pure
{
  ret y - 2
}
"""
FIXED_DEC = "fn dec(y Int) -> Int\n  pure\n{\n  ret y - 1\n}"


def test_invariant_binding_persists_after_patch(tmp_path) -> None:
    from sigil.harness.core import Harness

    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="codec")
    ih = info["invariants"]["round_trip"]
    assert h.verify_invariant(ih, inputs={"x": 4})["status"] == "fail"  # dec=y-2

    r = h.patch_snippet(info["fns"]["dec"], FIXED_DEC, inputs={"x": 4})
    assert r["invariants"][0]["status"] == "pass"

    # the contradiction from the report: a fresh verify must AGREE with the patch
    again = h.verify_invariant(ih, inputs={"x": 4})
    assert again["status"] == "pass", "invariant binding not persisted after patch"
    assert h.store.status(ih) == "verified"


# ---- minors ---------------------------------------------------------------


def test_from_pytest_handles_short_column_names() -> None:
    from sigil.lift.pytest_bridge import extract_drafts

    # the report's textbook table: names 'n,exp', expected column is 'exp'
    src = (
        "import pytest\n"
        "from m import scale\n\n"
        '@pytest.mark.parametrize("n,exp", [(2, 4), (3, 6)])\n'
        "def test_scale(n, exp):\n"
        "    assert scale(n) == exp\n"
    )
    drafts = extract_drafts(src, name="test_scale.py")
    assert len(drafts) == 1
    d = drafts[0]
    assert d["fn"] == "scale" and d["params"] == ["n"]
    assert "out == 4" in d["sg"]
    assert d["inputs"] == {"n": 2}


def test_migrate_accepts_store_flag(tmp_path) -> None:
    import os

    from sigil.store.repo import Store

    Store.create(tmp_path)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [sys.executable, "-m", "sigil.cli", "migrate", "--store", str(tmp_path)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert r.returncode == 0, r.stderr
    assert "format -> 2" in r.stdout


def test_failed_proposal_is_labelled_on_sheet(tmp_path) -> None:
    from sigil.harness.core import Harness

    h = Harness(tmp_path)
    f = tmp_path / "m.py"
    f.write_text("def triple(n):\n    return n * 3\n")
    h.lift(str(f))
    fn_hash = h.lifted_fns()["triple"]
    h.propose_contract(fn_hash, ["out == n * 4"], inputs={"n": 6})  # wrong -> fail
    sheet = h.sheet()
    assert "rejected" in sheet or "provisional" in sheet  # not just bare "proposed"
