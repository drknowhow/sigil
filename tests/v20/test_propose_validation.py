"""v2.0.2 — propose_contract must validate against GENERATED inputs, not the
proposer's single chosen witness (firstuse/V2_REPORT_addendum.md).

The exploit: an agent proposes a false rule AND the one input on which it
happens to hold; the old code bound it `verified`. Now a proposal can only
reach verified via independently generated/recorded inputs."""

from pathlib import Path

from sigil.harness.core import Harness

CLAMP = (
    "def clamp(x, lo, hi):\n"
    "    if x < lo:\n        return lo\n"
    "    if x > hi:\n        return hi\n"
    "    return x\n"
)
TRIPLE_TYPED = "def triple(n: int) -> int:\n    return n * 3\n"


def _lift(tmp_path: Path, src: str, name: str):
    h = Harness(tmp_path)
    f = tmp_path / f"{name}.py"
    f.write_text(src)
    h.lift(str(f))
    return h


def test_exploit_false_rule_does_not_bind_on_proposer_input(tmp_path) -> None:
    # the report's exact exploit: out == x passes at x=5 but is false in general
    h = _lift(tmp_path, CLAMP, "m")
    fn = h.lifted_fns()["clamp"]
    r = h.propose_contract(fn, ["out == x"], inputs={"x": 5, "lo": 0, "hi": 10})
    assert r["verify"]["status"] != "pass", r["verify"]
    assert h.store.status(r["goal_hash"]) == "provisional"  # MUST NOT bind
    # a counterexample was found by generation, not the proposer
    assert r["evidence"]["counterexamples"], r["evidence"]


def test_true_rule_binds_with_evidence(tmp_path) -> None:
    # clamp always returns one of x / lo / hi — a genuinely true property
    h = _lift(tmp_path, CLAMP, "m")
    fn = h.lifted_fns()["clamp"]
    r = h.propose_contract(
        fn, ["out == x or out == lo or out == hi"], inputs={"x": 5, "lo": 0, "hi": 10}
    )
    assert r["verify"]["status"] == "pass", r["verify"]
    assert h.store.status(r["goal_hash"]) == "verified"
    ev = r["evidence"]
    assert ev["supporting_cases"] >= 8 and ev["counterexamples"] == []


def test_typed_params_use_typed_generator(tmp_path) -> None:
    h = _lift(tmp_path, TRIPLE_TYPED, "m")
    fn = h.lifted_fns()["triple"]
    good = h.propose_contract(fn, ["out == n * 3"], inputs={"n": 4})
    assert good["verify"]["status"] == "pass"
    assert h.store.status(good["goal_hash"]) == "verified"
    assert good["evidence"]["method"] == "typed-generated"
    bad = h.propose_contract(fn, ["out == n"], inputs={"n": 0})  # passes only at 0
    assert bad["verify"]["status"] != "pass"
    assert h.store.status(bad["goal_hash"]) == "provisional"


def test_insufficient_evidence_when_generation_cannot_apply(tmp_path) -> None:
    # needs a dict; numeric/string probes all raise -> cannot claim verified
    h = _lift(tmp_path, "def getx(d):\n    return d['x']\n", "m")
    fn = h.lifted_fns()["getx"]
    r = h.propose_contract(fn, ["out == d"], inputs={"d": {"x": 1}})
    assert h.store.status(r["goal_hash"]) == "provisional"
    assert "insufficient" in str(r["verify"]).lower() or r["evidence"]["supporting_cases"] < 8


def test_sheet_shows_evidence_strength(tmp_path) -> None:
    h = _lift(tmp_path, TRIPLE_TYPED, "m")
    fn = h.lifted_fns()["triple"]
    h.propose_contract(fn, ["out == n * 3"], inputs={"n": 4})
    sheet = h.sheet()
    # 'verified' must be qualified by evidence, not a bare stamp
    assert "tier-3 verified" in sheet and "case" in sheet


def test_proposer_hint_alone_never_binds(tmp_path) -> None:
    # even with a passing hint, binding requires generated supporting cases
    h = _lift(tmp_path, CLAMP, "m")
    fn = h.lifted_fns()["clamp"]
    r = h.propose_contract(fn, ["out == x"], inputs={"x": 5, "lo": 0, "hi": 10})
    assert r["evidence"]["cases_generated"] > 1  # not just the one hint
