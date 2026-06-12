# SIGIL v1.0 — Build Plan for Claude Cowork

*Master guide for a Cowork session to build Sigil to fully functional, production-ready state.
Inputs: `sigil-spec.md` (v2.1), `sigil-roadmap.md`, `sigil_lift.py` (PoC seed), `demo_module.py`.*

---

## 1. Mission & definition of done

Build **Sigil v1.0**: a working system where (a) existing Python code can be *lifted* into Sigil's content-addressed, effect-annotated form; (b) new code can be *written* in Sigil and transpiled to runnable Python with contracts enforced; (c) an *MCP harness* lets an AI agent work on a Sigil codebase through digests and patches under rules R1–R3.

**Done means:** a developer can `pip install sigil`, run `sigil lift ./myrepo`, connect the MCP server to Claude Code, edit code through patches, write a new Sigil module, transpile it, and run it — with tests green, docs complete, and examples working end to end.

## 2. Scope

**In scope (v1.0):**
- Python frontend only (lift + transpile targets Python 3.11+)
- Lifter Tiers 1–2 (structure + effects); Tier 3 contract proposer as an *experimental* flag
- Sigil core language: functions, goals, contracts (pre/post/verify), effect rows, pure subset
- MCP harness: `digest`, `expand`, `patch`, `verify`, `lift` tools with append-only context (R1), patch-only edits, verify-before-display (R3)
- CLI, test suite, docs, examples

**Out of scope (do not build, note as v2 candidates):**
- TypeScript/R frontends, pure-core interpreter, dictionary learning, goal-template library beyond 3 starters, bidirectional sync (lift→edit→idiomatic lowering), any web UI

## 3. Repository layout

```
sigil/
├── pyproject.toml              # packaging, pinned deps (stdlib-first; minimal deps)
├── README.md                   # quickstart in <5 min
├── src/sigil/
│   ├── core/ast.py             # Sigil core AST nodes + CBOR/JSON serialization
│   ├── core/hash.py            # canonicalization + content addressing
│   ├── lift/python.py          # Tier 1: python ast -> Sigil AST (evolve from sigil_lift.py)
│   ├── lift/effects.py         # Tier 2: effect walker w/ assignment & call-graph propagation
│   ├── lift/contracts.py       # Tier 3 (experimental, behind --propose-contracts)
│   ├── lang/parser.py          # Sigil text projection -> AST (LL(1), no ambiguity)
│   ├── lang/printer.py         # AST -> text projection (lossless round-trip)
│   ├── transpile/python.py     # Sigil AST -> Python source + assertions
│   ├── transpile/effectcheck.py# static call-graph effect-budget check
│   ├── verify/runner.py        # executes verify clauses; caches by (goal_hash, impl_hash)
│   ├── harness/server.py       # MCP server (FastMCP), tools per §6
│   ├── harness/context.py      # append-only digest sheet (R1 enforcement)
│   ├── store/repo.py           # .sigil/ store: objects by hash, goal↔impl bindings
│   └── cli.py                  # sigil lift|build|verify|serve|sheet
├── tests/                      # mirrors src; see §7
├── examples/                   # see §9
└── docs/                       # see §8
```

## 4. Build phases (execute in order; each has a hard exit gate)

**Phase 0 — Foundations (core AST + hashing).**
Define the Sigil core AST (≈15 node types: Module, Goal, Fn, Contract, EffectRow, Patch…), serialization, canonicalization, hashing. Port the PoC's determinism property here.
*Exit gate:* property test passes — any formatting/comment/docstring change to source produces identical hashes; serialization round-trips byte-identically.

**Phase 1 — Lifter (Tiers 1–2).**
Evolve `sigil_lift.py`: full module lifting (functions, classes-as-records, imports), and **fix the known effect gap** — propagate effects through variable assignment and the call graph (the PoC misses `!fs` when I/O goes through a `Path` variable; this is the first test to write). Unknown dynamic calls emit `!unsafe?`, never silence.
*Exit gate:* lift a real 3k+ line OSS repo; digest sheet generated; effect rows spot-checked with <10% under-reporting on a hand-labeled 30-function sample. Under-reporting is the failure metric, not over-reporting.

**Phase 2 — Language + transpiler.**
Parser/printer for the text projection (grammar fixed in docs/grammar.md, written first), then transpile to Python: contracts → dev assertions (env-gated), goals → generated test modules, effect budgets → static call-graph rejection with a clear error message naming the violating call chain.
*Exit gate:* `examples/new-module/` written in Sigil transpiles, runs, and a deliberately over-budget effect is rejected at build time with an actionable error.

**Phase 3 — Verify runner + store.**
`.sigil/` object store; verify clauses execute in a subprocess with timeout; results cached by `(goal_hash, impl_hash)`; goal↔impl binding only on pass; `provisional` status for anything unverified.
*Exit gate:* re-running verify on unchanged code is a cache hit (<50 ms); a failing contract blocks binding and reports which clause failed with values.

**Phase 4 — MCP harness.**
FastMCP server exposing: `sheet()` (digest sheet), `expand(hash)`, `patch(hash, edits)` (returns new hash), `verify(goal)`, `lift(path)`. Enforce R1 (sheet is append-only per session; superseded entries append `old → new` lines), R2 (expand-over-regenerate guidance in tool descriptions), R3 (patch results are auto-verified; failures returned as structured feedback targeting the failing subtree). Consult the mcp-builder skill conventions.
*Exit gate:* a live Claude Code session lifts `demo_module.py`, reads only the sheet, fixes a seeded bug via `patch`, and verify confirms — with zero full-file reads or writes.

**Phase 5 — Hardening + release.**
Error handling (every CLI/tool error is actionable: what failed, why, what to try), logging (structured, quiet by default), `--json` output for all CLI commands, packaging, version pinning, CHANGELOG, semver.
*Exit gate:* production checklist (§10) fully green.

## 5. Working agreements for the Cowork session

- Write the test for each exit gate **before** the implementation it gates.
- No dependency without justification in a comment in pyproject; prefer stdlib. Expected deps: `cbor2`, `mcp`/`fastmcp`, `pytest`, `hypothesis`. That's likely all.
- Modular and legible over clever; each module independently testable; no file >400 lines without splitting.
- When a design question isn't settled by the spec/roadmap, choose the simpler option, implement it, and log the decision in `docs/decisions.md` rather than stalling.
- Never mark Tier 2/3 output as trusted; the `?` marker convention from the PoC is load-bearing.

## 6. MCP tool contract (freeze early — the harness is the product)

| Tool | In | Out | Rules |
|---|---|---|---|
| `lift` | path | sheet + stats | idempotent; re-lift detects changed hashes |
| `sheet` | — | digest lines | append-only within session (R1) |
| `expand` | hash | full projection | logs expansion for cost stats |
| `patch` | hash, edit ops | new hash, verify result | auto-verifies (R3); rejects malformed ops with location |
| `verify` | goal hash | pass/fail + clause detail | cached; subprocess-isolated; timeout |

## 7. Testing requirements

- **Unit tests** per module; target ≥85% line coverage on `core/`, `lift/`, `transpile/`.
- **Property tests (hypothesis):** hash stability under formatting noise; parser/printer round-trip (`print(parse(x)) == x` and `parse(print(ast)) == ast`); patch application = re-lift equivalence.
- **Golden files:** lifted output for `demo_module.py` and one OSS repo snapshot, checked verbatim.
- **Effect-inference benchmark:** 30 hand-labeled functions in `tests/fixtures/effects/`, asserting zero under-reports on the labeled set (the Path/`!fs` case from the PoC is fixture #1).
- **Integration:** full pipeline test — lift → patch → verify → transpile → execute.
- **Adversarial:** malformed patches, hash collisions on prefix (force 8-char fallback), `eval`/`getattr`-heavy code, contract that loops forever (timeout must catch).
- CI config (GitHub Actions) running all of the above on 3.11/3.12.

## 8. Documentation deliverables (in `docs/`)

1. `quickstart.md` — install → lift → first patch in 5 minutes
2. `grammar.md` — full text-projection grammar (written before Phase 2 code)
3. `language-guide.md` — goals, contracts, effects, with the fetch_prices example from the spec
4. `harness-guide.md` — connecting to Claude Code/Cowork; R1–R3 explained operationally
5. `lifting-guide.md` — what the tiers mean, reading `?` markers, when to trust what
6. `cost-model.md` — the v2.1 cost function, how to measure savings on your own repo
7. `decisions.md` — running log; `limitations.md` — honest list, seeded from the roadmap's risk register

## 9. Examples to ship (`examples/`)

1. **`lift-legacy/`** — a small flask-style app lifted; before/after context-cost numbers measured with a real tokenizer (not estimates — replace the spec's eyeballed counts and update docs with measured figures)
2. **`new-module/`** — the spec's `fetch_prices` goal written in Sigil, transpiled, run against a mocked API; includes the over-budget-effect failure demo
3. **`agent-session/`** — scripted transcript + harness logs of an AI fixing a seeded bug via patches only, with cost accounting per R1–R3
4. **`contracts-101/`** — `dedupe` with full pre/post, showing a wrong implementation caught by verify

## 10. Production-readiness checklist

- [ ] All phase exit gates green; CI green on supported Python versions
- [ ] `pip install` from a clean venv works; CLI `--help` complete; `--json` everywhere
- [ ] Every error message states cause + remedy; no raw tracebacks reach users
- [ ] Verify runs subprocess-isolated with timeouts (untrusted code never runs in-process)
- [ ] No secrets/paths leak into hashes or logs; store is relocatable
- [ ] Measured (not estimated) token-cost numbers in docs, with methodology
- [ ] `limitations.md` current — including: effects on heavily dynamic code, one-directional lifting, contract proposer experimental
- [ ] CHANGELOG + semver tag `v1.0.0`

## 11. Suggested session order & sizing

Phases 0–1 ≈ one focused session; Phase 2 ≈ one session (grammar first); Phases 3–4 ≈ one session; Phase 5 + docs + examples ≈ one session. If anything must be cut for time: Tier 3 proposer first, then example 3 — never the tests, never the harness.
