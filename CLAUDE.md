# CLAUDE.md — Sigil v1.0 Build

## What this project is
Sigil is a contract-first, content-addressed language + toolchain for human↔AI coding.
You are building it to production-ready v1.0. The authoritative documents, in priority order:

1. `docs/plan/sigil-cowork-plan.md` — master build plan: scope, repo layout, phases, exit gates. **Follow it.**
2. `docs/plan/sigil-spec.md` — language spec v2.1 (goals, contracts, effects, R1–R3 cost rules)
3. `docs/plan/sigil-roadmap.md` — lifter architecture, trust tiers, risk register
4. `seed/sigil_lift.py` + `seed/demo_module.py` — PoC to evolve into src/sigil/lift/python.py; do not start from scratch

## Hard rules (non-negotiable)
- **Tests before implementation.** Every phase exit gate in the plan §4 is written as a failing test first.
- **Scope discipline.** Plan §2 "out of scope" items are forbidden in v1.0. Log ideas in `docs/decisions.md` instead.
- **Never silence uncertainty.** Tier-2/3 outputs keep their `?` / `provisional` markers end to end. Under-reporting an effect is a bug; over-reporting is acceptable.
- **Untrusted code never runs in-process.** Verify clauses and lifted code execute subprocess-isolated with timeouts.
- **No dependency without a justification comment** in pyproject. Expected: cbor2, fastmcp/mcp, pytest, hypothesis. Stdlib otherwise.
- **No file >400 lines** — split it. Modular, legible, independently testable.
- When the spec/plan doesn't settle a design question: pick the simpler option, implement, record in `docs/decisions.md`. Do not stall, do not ask unless it changes scope.

## Commands
```bash
pip install -e ".[dev]"        # setup
pytest -q                      # full suite (must stay green at every commit)
pytest tests/properties -q     # hash-stability + round-trip property tests
sigil lift <path>              # lift python -> digest sheet
sigil build <module.sg>        # transpile to python (static effect check runs here)
sigil verify <goal-hash>       # run verify clauses (cached by goal+impl hash)
sigil serve                    # MCP harness
ruff check src tests && ruff format --check src tests
```

## Code conventions
- Python 3.11+, full type hints, dataclasses for AST nodes
- Errors: every user-facing failure states cause + remedy; never a raw traceback
- Logging: structured, quiet by default; `--json` on every CLI command
- Commits: one logical change each; message references plan phase (e.g. `phase1: propagate effects through assignments`)

## Project skills (in .claude/skills/ — consult before the matching work)
- `sigil-canonical-hashing` — before touching core/ast.py, core/hash.py, or any canonicalization
- `sigil-effect-inference` — before touching lift/effects.py or effect fixtures
- `sigil-transpile-verify` — before lang/, transpile/, or verify/ work
- `sigil-harness-rules` — before harness/ work (use with the mcp-builder skill)
- `sigil-quality-gates` — before claiming any phase complete or cutting a release

## Current phase tracking
Maintain `docs/STATUS.md`: current phase, gate test status, blockers. Update it every session start and end.

## Definition of done (v1.0)
Plan §10 checklist fully green. If time forces cuts: Tier-3 proposer first, then example 3.
Never cut tests. Never cut the harness.
