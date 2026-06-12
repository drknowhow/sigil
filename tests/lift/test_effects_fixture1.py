"""Fixture #1 — the PoC's known miss (sigil-effect-inference skill).

`p = CACHE / f"{t}.json"; p.read_text()` must infer !fs via origin
propagation through assignment. This must pass before anything else in
Phase 1 is considered done.
"""

from pathlib import Path

from sigil.lift.python import lift_source

FIXTURE = Path(__file__).parent.parent / "fixtures" / "effects" / "case_001.py"


def test_path_variable_io_is_not_missed() -> None:
    lifted = lift_source(FIXTURE.read_text(), name="case_001")
    fn = next(d for d in lifted.module.defs if getattr(d, "name", None) == "fetch_cached")
    names = {e.name for e in fn.fx.effects}
    assert "fs" in names, f"under-reported !fs; got row: {fn.fx}"
