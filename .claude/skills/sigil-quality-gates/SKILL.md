---
name: sigil-quality-gates
description: Phase exit gates, testing strategy, and the production-readiness checklist for the Sigil build. ALWAYS consult before declaring any phase complete, before tagging or packaging a release, when structuring the test suite, when adding or updating golden files, and at the start of every session to decide what to work on (it defines STATUS.md discipline). Also use whenever tempted to cut scope.
---

# Sigil Quality Gates

## Session discipline
- Session start: read docs/STATUS.md, run `pytest -q`, confirm green before new work. If red, fixing red IS the work.
- Session end: update STATUS.md (phase, gate-test status, blockers, next action).

## Gate-test-first protocol
Each phase in plan section 4 has an exit gate, implemented as a test in `tests/gates/test_phase{N}.py`, written and failing BEFORE phase implementation begins. A phase is complete only when its gate test passes in CI — not when it "works locally".

| Phase | Gate (summary) |
|---|---|
| 0 | hash-stability properties + byte-identical serialization round-trip |
| 1 | real OSS repo lifts; effects fixture set: zero under-reports |
| 2 | example module transpiles and runs; over-budget effect rejected with golden error |
| 3 | failing contract blocks binding; verify cache hit <50ms |
| 4 | scripted agent session: bug fixed via patches only, zero full-file reads/writes |
| 5 | plan section 10 checklist green |

## Test taxonomy & locations
- `tests/unit/` mirrors src; >=85% line coverage on core/, lift/, transpile/ (fail-under enforced in CI).
- `tests/properties/` — hypothesis: hash stability, round-trips, patch == re-lift equivalence.
- `tests/golden/` — lifted demo_module.py sheet, OSS repo sheet snapshot, the effect-budget error message. Golden updates require a decisions.md entry explaining why.
- `tests/fixtures/effects/` — numbered labeled cases; case_001 is the Path/!fs miss from the PoC.
- `tests/adversarial/` — malformed patches, 4-char prefix collisions (assert 8-char escalation), eval/getattr-heavy code, infinite-loop contract (assert timeout fires).
- `tests/integration/test_pipeline.py` — lift -> patch -> verify -> transpile -> execute.

## Measured, not estimated
Example 1 (lift-legacy) must compute token counts with a real tokenizer and write the measured numbers into docs/cost-model.md, replacing all estimates from the spec era. If measurements contradict the spec's claims, docs state the measured number — the spec is marketing until measured.

## Release checklist (plan section 10) — verify each line literally before tagging
clean-venv pip install; CLI --help and --json complete; errors actionable (test that no raw traceback reaches stdout); subprocess isolation on verify; no secrets/absolute paths in hashes or logs (test with a tmpdir-relocated store); limitations.md current; CHANGELOG; tag v1.0.0.

## When tempted to cut
Allowed cuts, in order: Tier-3 proposer, then example 3. Forbidden cuts: any test category, the harness, R1 enforcement. This is plan section 11 and is not negotiable.
