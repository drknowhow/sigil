"""v1.2 gate: property generation from typed contracts; counterexamples recorded."""

from sigil.harness.core import Harness
from sigil.verify.propgen import generate_inputs, run_property_check

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
  ret n * 3
}
"""
SNEAKY = SG.replace(
    "{\n  ret n * 3\n}",
    "{\n  if n > 50 {\n    ret 0\n  }\n  ret n * 3\n}",
)


def test_generators_cover_typed_params(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="m")
    goal = h.store.get(info["goals"]["triple"])
    cases = generate_inputs(goal, n=20, seed=42)
    assert len(cases) == 20
    assert all(isinstance(c["n"], int) for c in cases)
    assert cases == generate_inputs(goal, n=20, seed=42)  # deterministic


def test_property_check_passes_clean_impl(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG, name="m")
    report = run_property_check(h.store, info["goals"]["triple"], n=25, seed=7)
    assert report["status"] == "pass" and report["cases"] == 25


def test_counterexample_found_and_recorded(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(SNEAKY, name="m")
    gh = info["goals"]["triple"]
    report = run_property_check(h.store, gh, n=60, seed=7)
    assert report["status"] == "fail"
    cx = report["counterexamples"]
    assert cx and all(c["n"] > 50 for c in cx)
    # permanent: the counterexample is now a recorded input for future verifies
    recorded = h.store.recorded_inputs(gh)
    assert recorded is not None and recorded["n"] > 50
