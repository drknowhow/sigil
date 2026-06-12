"""Tier 1 lifting: structure, idempotence, formatting invariance, records."""

from pathlib import Path

from sigil.core.ast import Fn, Record
from sigil.lift.python import lift_source

DEMO = (Path(__file__).parent.parent.parent / "seed" / "demo_module.py").read_text()


def test_demo_module_lifts_all_functions() -> None:
    lifted = lift_source(DEMO, name="demo_module")
    fns = [d for d in lifted.module.defs if isinstance(d, Fn)]
    assert {f.name for f in fns} == {"fetch_prices", "dedupe", "moving_average", "jitter_backoff"}
    assert any(i.module == "requests" for i in lifted.module.imports)


def test_demo_module_expected_effects() -> None:
    lifted = lift_source(DEMO, name="demo_module")
    rows = {d.name: {e.name for e in d.fx.effects} for d in lifted.module.defs if isinstance(d, Fn)}
    assert {"net", "fs"} <= rows["fetch_prices"]  # the PoC missed fs — never again
    assert "rand" in rows["jitter_backoff"]
    assert rows["dedupe"] == set()  # pure?
    assert rows["moving_average"] == set()


def test_lift_is_idempotent() -> None:
    a = lift_source(DEMO, name="demo_module")
    b = lift_source(DEMO, name="demo_module")
    assert [e.digest for e in a.entries] == [e.digest for e in b.entries]


def test_formatting_change_does_not_move_digests() -> None:
    noisy = DEMO.replace("\n\ndef dedupe", "\n# a comment\n\n\ndef dedupe")
    assert noisy != DEMO
    a = lift_source(DEMO, name="demo_module")
    b = lift_source(noisy, name="demo_module")
    assert {e.name: e.digest for e in a.entries} == {e.name: e.digest for e in b.entries}


def test_semantic_change_moves_only_that_digest() -> None:
    changed = DEMO.replace("min(60.0,", "min(30.0,")
    a = {e.name: e.digest for e in lift_source(DEMO, name="d").entries}
    b = {e.name: e.digest for e in lift_source(changed, name="d").entries}
    assert a["jitter_backoff"] != b["jitter_backoff"]
    same = set(a) - {"jitter_backoff"}
    assert all(a[k] == b[k] for k in same)


def test_classes_lift_as_records() -> None:
    src = '''
class Point:
    """A 2-D point."""
    x: float
    y: float

    def dist2(self) -> float:
        return self.x ** 2 + self.y ** 2
'''
    lifted = lift_source(src, name="m")
    recs = [d for d in lifted.module.defs if isinstance(d, Record)]
    assert len(recs) == 1
    assert recs[0].name == "Point"
    assert {f.name for f in recs[0].fields} == {"x", "y"}
    assert {m.name for m in recs[0].methods} == {"dist2"}


def test_syntax_error_is_actionable() -> None:
    import pytest

    with pytest.raises(ValueError, match="Remedy"):
        lift_source("def broken(:\n  pass", name="bad")
