"""v2.0 gates: multi-fn invariants (P3.9) + Tier-3 propose/validate + bridge."""

from sigil.harness.core import Harness

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
  ret x * 2 + 1
}

fn dec(y Int) -> Int
  pure
{
  ret (y - 1) // 2
}
"""


def test_invariant_parses_prints_and_verifies(tmp_path) -> None:
    from sigil.lang.parser import parse_module
    from sigil.lang.printer import print_module

    mod = parse_module(SG)
    inv = mod.defs[0]
    assert inv.over == ["enc", "dec"]
    assert print_module(parse_module(print_module(mod))) == print_module(mod)

    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="codec")
    assert "round_trip" in info["invariants"]
    v = h.verify_invariant(info["invariants"]["round_trip"], inputs={"x": 21})
    assert v["status"] == "pass"


def test_patching_either_fn_reverifies_invariant(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="codec")
    r = h.patch_snippet(
        info["fns"]["enc"], "fn enc(x Int) -> Int\n  pure\n{\n  ret x * 3 + 1\n}", inputs={"x": 21}
    )
    invs = r.get("invariants")
    assert invs and invs[0]["name"] == "round_trip"
    assert invs[0]["status"] == "fail"  # dec no longer inverts enc


def test_propose_contract_validates_before_binding(tmp_path) -> None:
    h = Harness(tmp_path)
    f = tmp_path / "m.py"
    f.write_text("def triple(n):\n    return n * 3\n")
    h.lift(str(f))
    fn_hash = h.lifted_fns()["triple"]

    good = h.propose_contract(fn_hash, ["out == n * 3"], inputs={"n": 6})
    assert good["verify"]["status"] == "pass"
    assert h.store.status(good["goal_hash"]) == "verified"

    wrong = h.propose_contract(fn_hash, ["out == n * 4"], inputs={"n": 6})
    assert wrong["verify"]["status"] == "fail"
    assert h.store.status(wrong["goal_hash"]) == "provisional"  # never silently binds


def test_pytest_bridge_emits_reviewable_drafts(tmp_path) -> None:
    from sigil.lift.pytest_bridge import extract_drafts

    test_src = """
import pytest
from mymod import scale

@pytest.mark.parametrize(("value", "factor", "expected"), [(2, 3, 6), (5, 0, 0)])
def test_scale(value, factor, expected):
    assert scale(value, factor) == expected
"""
    drafts = extract_drafts(test_src, name="test_scale.py")
    assert len(drafts) == 1
    d = drafts[0]
    assert d["fn"] == "scale" and d["params"] == ["value", "factor"]
    assert "out == 6" in d["sg"] and "REVIEW" in d["sg"]
    assert d["inputs"] == {"value": 2, "factor": 3}
    assert d["cases"] == [
        {"value": 2, "factor": 3, "expected": 6},
        {"value": 5, "factor": 0, "expected": 0},
    ]
