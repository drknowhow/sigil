#!/usr/bin/env python3
"""Phase 2 exit-gate demo: a module written in Sigil transpiles, runs against
a mocked API, and an over-budget effect is rejected at build time."""

import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from sigil.transpile.build import BuildError, build_source  # noqa: E402

# --- 1. build prices.sg ----------------------------------------------------
result = build_source((HERE / "prices.sg").read_text(), name="prices.sg")
build_dir = HERE / "build"
build_dir.mkdir(exist_ok=True)
(build_dir / "prices.py").write_text(result.python_src)
for name, src in result.test_modules.items():
    (build_dir / f"{name}.py").write_text(src)
print("built prices.sg ->", ", ".join(["prices.py", *result.test_modules]))


# --- 2. mock the API and run the generated module --------------------------
class _Resp:
    def __init__(self, ticker: str) -> None:
        self._t = ticker

    def json(self) -> dict:
        return {"ticker": self._t, "bars": [{"o": 1, "h": 2, "l": 0.5, "c": 1.5, "v": 100}]}


mock = types.ModuleType("requests")
mock.get = lambda url: _Resp(url.rsplit("/", 1)[-1])
sys.modules["requests"] = mock

sys.path.insert(0, str(build_dir))
import prices  # noqa: E402  (generated)
import test_fetch_prices  # noqa: E402  (generated)

inputs = {"tickers": ["AAPL", "MSFT"], "start": "2026-01-01", "end": "2026-06-01"}
out = prices.fetch_prices(**inputs)
print("fetch_prices ->", sorted(out))

checks = test_fetch_prices.run_verify(out, **inputs)
assert all(ok for _, ok in checks), checks
print("verify: all clauses passed:", [c for c, _ in checks])

# --- 3. the over-budget variant must be rejected ---------------------------
try:
    build_source((HERE / "over_budget.sg").read_text(), name="over_budget.sg")
except BuildError as exc:
    print("over_budget.sg rejected as expected:")
    print(str(exc))
else:
    sys.exit("ERROR: over-budget effect was NOT rejected")
