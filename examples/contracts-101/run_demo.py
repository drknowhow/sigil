#!/usr/bin/env python3
"""contracts-101 (plan section 9, example 4): a wrong implementation is
caught by verify; the right one binds. Run me directly."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.dont_write_bytecode = True

from sigil.harness.core import Harness  # noqa: E402

GOOD = (Path(__file__).parent / "dedupe.sg").read_text()
BAD = GOOD.replace("ret [x | x <- xs, s.insert(x)]", "ret xs")  # keeps duplicates
INPUTS = {"xs": [3, 1, 3, 2, 1]}

with tempfile.TemporaryDirectory() as tmp:
    h = Harness(tmp)
    info = h.load_sigil_source(BAD, name="dedupe101")
    v = h.verify(info["goals"]["dedupe"], inputs=INPUTS)
    print(f"wrong implementation: {v['status']}")
    for text, ok, detail in v["clauses"]:
        print(f"  [{'ok' if ok else 'FAIL'}] {text}" + (f" — {detail}" if detail else ""))
    assert v["status"] == "fail" and v["goal_status"] == "provisional"

with tempfile.TemporaryDirectory() as tmp:
    h = Harness(tmp)
    info = h.load_sigil_source(GOOD, name="dedupe101")
    v = h.verify(info["goals"]["dedupe"], inputs=INPUTS)
    print(f"\ncorrect implementation: {v['status']} -> goal {v['goal_status']}")
    assert v["status"] == "pass" and v["goal_status"] == "verified"

print("\ncontracts-101: the spec is executable — wrong code cannot bind.")
