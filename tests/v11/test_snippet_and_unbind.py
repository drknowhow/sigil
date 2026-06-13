"""v1.1 gates: patch-by-snippet (== re-lift), unbind tombstones, store diff."""

from sigil.core.ast import to_data
from sigil.core.patch import diff_data
from sigil.harness.core import Harness
from sigil.store.diff import store_diff
from sigil.store.repo import Store

SG = """module m

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

FIXED_FN = "fn triple(n Int) -> Int\n  pure\n{\n  ret n * 3\n}"


def test_snippet_diff_is_minimal_and_equals_relift(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="m")
    old = h.store.get(info["fns"]["triple"])
    from sigil.lang.parser import parse_module

    new_fn = parse_module("module _s\n\n" + FIXED_FN + "\n").defs[0]
    ops = diff_data(to_data(old), to_data(new_fn))
    assert len(ops) == 1 and ops[0]["op"] == "replace"
    assert ops[0]["path"].endswith(".val")

    r = h.patch_snippet(info["fns"]["triple"], FIXED_FN, inputs={"n": 5})
    assert r["verify"]["status"] == "pass"
    assert r["new_hash"] == h.store.put(new_fn)  # snippet == re-lift, by hash


def test_snippet_on_lifted_python(tmp_path) -> None:
    h = Harness(tmp_path)
    f = tmp_path / "m.py"
    f.write_text("def half(n):\n    return n / 3\n")
    h.lift(str(f))
    fn_hash = h.lifted_fns()["half"]
    r = h.patch_snippet(fn_hash, "def half(n):\n    return n / 2\n")
    assert r["verify"] == "unverified: no goal bound"
    assert "return n / 2" in h.expand(r["new_hash"])


def test_snippet_name_mismatch_is_actionable(tmp_path) -> None:
    import pytest

    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="m")
    with pytest.raises(ValueError, match="(?s)name.*Remedy"):
        h.patch_snippet(info["fns"]["triple"], "fn other(n Int) -> Int\n  pure\n{\n  ret n\n}")


def test_unbind_tombstone_lifecycle(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="m")
    h.patch_snippet(info["fns"]["triple"], FIXED_FN, inputs={"n": 2})  # binds
    gh = info["goals"]["triple"]
    assert h.store.status(gh) == "verified"
    h.store.unbind(gh, reason="contract retired in favor of triple_v2")
    assert h.store.status(gh) == "retired"
    desc = h.store.describe_goal(gh)
    assert "retired" in desc and "triple_v2" in desc
    assert h.store.binding(gh) is None


def test_store_diff_reports_transitions(tmp_path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    ha = Harness(a)
    ha.load_sigil_source(SG, name="m")
    hb = Harness(b)
    info = hb.load_sigil_source(SG, name="m")
    hb.patch_snippet(info["fns"]["triple"], FIXED_FN, inputs={"n": 2})  # binds in b
    d = store_diff(Store.open(a), Store.open(b))
    assert any("triple" in g for g in d["bound"])
    assert d["unbound"] == [] and d["dropped"] == []
