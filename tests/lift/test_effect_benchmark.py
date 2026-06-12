"""Effect-inference benchmark over the hand-labeled fixture set (plan section 7).

Gate: zero under-reports. Over-report rate is informational (target <25%).
Scoring (sigil-effect-inference skill):
- a labeled effect is covered if inferred directly, or if the row contains
  !unsafe (the honest "all bets off" marker);
- 'pure' labels cannot be under-reported; anything inferred there is an
  over-report;
- labels with '?' (e.g. '!unsafe?') additionally require the uncertainty
  marker to survive — it must never be silenced.
"""

import json
from pathlib import Path

import pytest

from sigil.lift.python import lift_source

FIXTURES = sorted((Path(__file__).parent.parent / "fixtures" / "effects").glob("case_*.py"))


def _rows(path: Path) -> dict[str, object]:
    lifted = lift_source(path.read_text(), name=path.stem)
    out = {}

    def collect(defs):
        for d in defs:
            if hasattr(d, "fx"):
                out[d.name] = d.fx
            if hasattr(d, "methods"):
                collect(d.methods)

    collect(lifted.module.defs)
    return out


def test_fixture_set_is_complete() -> None:
    assert len(FIXTURES) >= 30, "benchmark requires >=30 labeled functions"


@pytest.mark.parametrize("case", FIXTURES, ids=lambda p: p.stem)
def test_no_under_reporting(case: Path) -> None:
    labels = json.loads(case.with_suffix("").with_suffix(".labels.json").read_text())
    rows = _rows(case)
    for fname, expected in labels.items():
        assert fname in rows, f"{case.stem}: function {fname!r} not lifted"
        row = rows[fname]
        inferred = {e.name for e in row.effects}
        for label in expected:
            if label == "pure":
                continue
            base = label.lstrip("!").rstrip("?")
            assert base in inferred or "unsafe" in inferred, (
                f"{case.stem}:{fname}: UNDER-REPORT — labeled {label}, "
                f"inferred {sorted(inferred) or 'pure?'}"
            )
            if label.endswith("?") and base in inferred:
                eff = next(e for e in row.effects if e.name == base)
                assert eff.uncertain, f"{case.stem}:{fname}: '?' marker silenced on {label}"


def test_over_report_rate_informational() -> None:
    over = total = 0
    detail = []
    for case in FIXTURES:
        labels = json.loads(case.with_suffix("").with_suffix(".labels.json").read_text())
        rows = _rows(case)
        for fname, expected in labels.items():
            bases = {lbl.lstrip("!").rstrip("?") for lbl in expected if lbl != "pure"}
            inferred = {e.name for e in rows[fname].effects}
            total += max(1, len(bases))
            extra = inferred - bases - {"unsafe"}
            if extra:
                over += len(extra)
                detail.append(f"{case.stem}:{fname} +{sorted(extra)}")
    rate = over / total if total else 0.0
    print(f"\nover-report rate: {rate:.1%} ({over}/{total}); " + "; ".join(detail))
    assert rate < 0.25, f"over-report rate {rate:.1%} exceeds informational target"
