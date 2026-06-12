"""Golden file: the demo_module digest sheet, checked verbatim (plan section 7).

PoC ast.dump digests were replaced by canonical-CBOR digests when Phase 0
landed; goldens regenerated once (decisions.md D-007).
"""

from pathlib import Path

from sigil.lift.python import lift_source, render_sheet

ROOT = Path(__file__).parent.parent.parent
GOLDEN = Path(__file__).parent / "demo_module.sheet"


def test_demo_sheet_matches_golden() -> None:
    src = (ROOT / "seed" / "demo_module.py").read_text()
    sheet = render_sheet(lift_source(src, name="demo_module"), source_path="seed/demo_module.py")
    assert GOLDEN.exists(), "golden missing — generate once implementation is green"
    assert sheet == GOLDEN.read_text()
