"""v1.2 gates: recorded inputs (D-020 revisited) + inputs-aware verdict cache."""

from sigil.harness.core import Harness
from sigil.verify.runner import run_verify

SG = """module m

goal triple {{
  intent: "triples"
  in: n Int
  out: Int
  fx: pure
  inputs: "{ref}"
  verify:
    out == n * 3
}}

fn triple(n Int) -> Int
  pure
{{
  ret n * 3
}}
"""


def test_goal_inputs_ref_resolves_from_store_root(tmp_path) -> None:
    (tmp_path / "triple.inputs.json").write_text('{"n": 7}')
    h = Harness(tmp_path)
    info = h.load_sigil_source(SG.format(ref="triple.inputs.json"), name="m")
    v = h.verify(info["goals"]["triple"], inputs=None)  # no caller inputs needed
    assert v["status"] == "pass"
    assert h.store.status(info["goals"]["triple"]) == "verified"


def test_inline_recorded_inputs_from_registry(tmp_path) -> None:
    h = Harness(tmp_path)
    info = h.load_sigil_source(
        SG.format(ref="x.json").replace('  inputs: "x.json"\n', ""), name="m"
    )
    gh = info["goals"]["triple"]
    h.store.record_inputs(gh, {"n": 3})
    v = h.verify(gh, inputs=None)
    assert v["status"] == "pass"


def test_cache_key_includes_inputs(tmp_path) -> None:
    from sigil.lang.parser import parse_module
    from sigil.store.repo import Store

    store = Store.create(tmp_path)
    mod = parse_module(SG.format(ref="i.json").replace('  inputs: "i.json"\n', ""))
    v1 = run_verify(store, mod, "triple", inputs={"n": 4})
    v2 = run_verify(store, mod, "triple", inputs={"n": 5})
    assert not v2.cached  # different inputs must not hit the old verdict
    v3 = run_verify(store, mod, "triple", inputs={"n": 4})
    assert v3.cached and v3.status == v1.status == "pass"
