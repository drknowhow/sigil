---
name: sigil-effect-inference
description: Effect inference (Tier 2) rules and algorithm for the Sigil lifter. ALWAYS consult before writing or modifying src/sigil/lift/effects.py, effect fixtures, the effect benchmark, or the transpiler's static effect-budget check. Also use whenever a test shows a missing or wrong effect row (!net, !fs, !rand, !clock, !env, !io, !mut, !unsafe), or when handling dynamic Python (getattr, eval, monkeypatching).
---

# Sigil Effect Inference

## Prime directive
**Zero under-reporting on the labeled fixture set.** Over-reporting (claiming !fs where there is none) is acceptable noise; under-reporting (missing real I/O) is a security bug — the entire effect-budget feature rests on it. When uncertain, emit `!unsafe?`, never nothing.

## Known failure to fix first (fixture #1)
The PoC misses `!fs` in:
```python
p = CACHE / f"{t}.json"        # CACHE: pathlib.Path
if p.exists(): out = json.loads(p.read_text())
```
Root cause: effects were keyed on the *call root name* only (`p`), with no origin tracking. This exact snippet is `tests/fixtures/effects/case_001.py` and must pass before anything else in Phase 1 is considered done.

## Algorithm (v1.0)
1. **Import map**: module/name -> base effect (requests/httpx/urllib/socket/aiohttp -> !net; pathlib/shutil/tempfile/open -> !fs; random/secrets -> !rand; time/datetime.now/today -> !clock; os.environ -> !env (os.path is pure); print/input/logging -> !io; subprocess/eval/exec/ctypes -> !unsafe).
2. **Origin propagation (intra-function)**: forward-propagate tainted origins through assignments — `p = CACHE / x` makes `p` pathlib-origin, so `p.read_text()` => !fs. Simple abstract interpretation over assignments and calls; attribute access preserves origin; binary ops on a tainted origin preserve it (Path / str -> Path).
3. **Call-graph propagation (inter-function)**: a function's row = own effects UNION rows of resolvable callees. Iterate to fixpoint (cycles are fine: union is monotone).
4. **Unresolvable** (getattr dispatch, functions passed as values, eval, unknown imports): emit `!unsafe?` on that function and stop pretending.
5. **!mut**: `global`/`nonlocal` writes, or mutation of module-level objects.

## Output conventions
- `pure?` not `pure` from static analysis — `?` means "static guess". Only a dynamic tracer (future) or human review may strip `?`. Never strip it in printing/formatting code paths.
- Effects sort alphabetically within a row for stable digests.

## Benchmark protocol
`tests/fixtures/effects/` holds >=30 hand-labeled functions (label file alongside each). The gate test asserts: under-reports == 0; over-report rate is reported (target <25%, informational). Every newly discovered miss becomes a numbered fixture *before* it is fixed.
