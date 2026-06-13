"""Unit-level fixes from the first-use report (N2, N3, N5, N6)."""

from pathlib import Path

from sigil.harness.core import Harness
from sigil.lift.python import lift_source

ROOT = Path(__file__).parent.parent.parent

SG = """module mathx

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
  ret n * 2
}
"""


def test_n2_existing_store_goals_appear_on_fresh_session_sheet(tmp_path) -> None:
    h1 = Harness(tmp_path)
    h1.load_sigil_source(SG, name="mathx")
    # a brand-new session over the same store must surface the goal (discovery)
    h2 = Harness(tmp_path)
    sheet = h2.sheet()
    assert "goal triple" in sheet and "provisional" in sheet


def test_n6_patch_returns_display_hash_too(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="mathx")
    r = h.patch(
        info["fns"]["triple"],
        [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}],
        inputs={"n": 2},
    )
    assert len(r["new_hash"]) == 64
    assert r["display"].startswith("#") and r["new_hash"].startswith(r["display"][1:5])


def test_n3_expand_canonical_form_shows_patchable_paths(tmp_path) -> None:
    h = Harness(tmp_path)
    src = tmp_path / "m.py"
    src.write_text("def half(n):\n    return n / 2\n")
    h.lift(str(src))
    fn_hash = h.lifted_fns()["half"]
    source_form = h.expand(fn_hash)
    assert "return n / 2" in source_form  # default: readable source
    canon = h.expand(fn_hash, form="canonical")
    assert '"body"' in canon and '"def"' in canon  # IR patch-path schema visible


def test_n5_sigil_scaffolding_filtered_from_sheets() -> None:
    src = "def __sigil_set_insert(s, x):\n    return True\n\ndef real_fn(x):\n    return x\n"
    result = lift_source(src, name="gen")
    names = [e.name for e in result.entries]
    assert "real_fn" in names
    assert "__sigil_set_insert" not in names  # generated scaffolding, not user code
