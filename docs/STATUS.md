# STATUS

## Session 2026-06-12 (published)

- **Repository:** https://github.com/drknowhow/sigil (private; verified anonymous
  access 404s). Initial import pushed by the user's agent (392d6b2); v1.0.1 tag
  created locally — push pending from a credentialed machine.

## Session 2026-06-12 (v1.0.1 — first-use report fixes)

- **External first-use report received** (firstuse/FIRST_USE_REPORT.md) — first real
  user drove `sigil serve` over actual stdio MCP. Disposition: firstuse/RESPONSE.md.
- **Critical fix:** served verify deadlocked (verify child inherited the server's
  stdin = the JSON-RPC pipe; also a read-traffic security hole). stdin=DEVNULL
  (D-029) + regression test through a real stdio ClientSession — closing the
  in-process-only blind spot the report correctly called out.
- **MCP surface:** load_module(source) tool added; sessions seed the sheet from the
  store's registered goals; expand(hash, form="canonical") exposes patch-path schema
  (D-030). Scaffolding filtered from sheets; patch returns display hash (D-031).
- **Distribution renamed sigil-lang** (PyPI "sigil" is taken — explains the v1.27.0
  shadow install in the report; D-032). Version 1.0.1; CHANGELOG updated.
- **Suite:** 136 tests green (2 via live stdio serve); ruff clean.


## Session 2026-06-12 (Phase 5 end — v1.0.0)

- **Phase 5 complete; v1.0.0 cut.** Plan §10 checklist verified line by line:
  - [x] all phase exit gates green; CI matrix 3.11/3.12 with 85% coverage floor (measured 92%)
  - [x] clean-venv pip install works; console script `sigil`; --help on every command;
        --json on lift/build/verify (serve speaks MCP) — tested
  - [x] errors actionable: no-traceback test over bad invocations; top-level entry guard
  - [x] verify subprocess-isolated + timeout (tests); untrusted code never in-process
  - [x] no absolute paths persisted in the store (test); store relocation test
  - [x] measured token numbers in docs/cost-model.md with methodology (D-027)
  - [x] limitations.md current (10 items, incl. verify network-blocking gap)
  - [x] CHANGELOG.md + version 1.0.0 (tag when pushed to a remote)
- **Suite:** 130 tests; ruff clean. Examples 1–4 all present and runnable.
- **Analyzer improvement during Phase 5 (D-025):** return-taint propagation;
  fixtures case_032/033; requests golden regenerated (Session.close now flagged).
- **Cut:** Tier-3 proposer (D-026, plan-sanctioned).
- **Folder cleanup:** root-level duplicate plan docs/seeds removed; caches purged;
  site/index.html added (project hero page with measured results).
- **Post-release additions:** site/index.html gained a Quick Guide tab (setup, CLI,
  MCP wiring for Claude Code/Desktop/Cowork, patch-op reference, troubleshooting);
  new `.claude/skills/sigil-agent-workflow` — the user-facing skill for agents driving
  `sigil serve` (the other five skills govern developing Sigil itself).
- **video/**: Remotion explainer (75s, 8 scenes, real numbers only) — type-checked
  against Remotion 4; preview `npm run studio`, render `npm run render` (needs local
  Chrome; the sandbox cannot download it).
- **Next:** v1.1 candidates live in decisions.md (Tier-3 proposer, scope enforcement,
  dynamic tracing, bidirectional lowering). Run a live Claude Code session against
  `sigil serve` (D-023) as user-facing validation.


## Session 2026-06-12 (Phase 4 end)

- **Phase 4 complete** (MCP harness) — exit gate green in scripted form (D-023).
- **Suite:** 119 tests passing; ruff clean.
- **R1:** harness/context.py SessionSheet — hypothesis property proves prefix-stability
  over arbitrary op sequences; supersede appends '#old -> #new', old lines stay;
  compaction only at session_close (for the next session).
- **R2:** expand() byte-identical per hash, expansions logged for cost stats; tool
  descriptions instruct expand-over-regenerate.
- **R3:** patch() auto-verifies; failures return failing clause + observed values +
  target subtree hash, small (<300 tok); "unverified: no goal bound" stated explicitly.
- **Patch engine:** core/patch.py (dotted data paths, op-index errors, D-021);
  core/pycanon gained uncanon/host_source (lifted-code projection for expand).
- **Tools:** lift / sheet / expand / patch / verify / session_close on FastMCP
  (`sigil serve --root DIR`); contract matches the frozen table in sigil-harness-rules.
- **examples/agent-session/:** scripted transcript + R1-R3 cost accounting
  (sheet 14 tok vs full file 42 tok; patch output 18 tok), regenerable via run_session.py.
- **Next phase:** 5 — hardening + release: docs (quickstart, language-guide,
  harness-guide, lifting-guide, cost-model with MEASURED tokenizer numbers),
  examples 1 (lift-legacy) and 4 (contracts-101), CHANGELOG, packaging, §10 checklist.
  Consult sigil-quality-gates before claiming completion.
- Decisions through D-024 logged.


## Session 2026-06-12 (Phase 3 end)

- **Phase 3 complete** (verify runner + store) — exit gate green.
- **Suite:** 103 tests passing; ruff clean.
- **Exit gate:** unchanged code re-verify is a cache hit measured <50ms (gate test);
  a failing contract blocks binding and reports the failing clause text with out/input
  values; an infinite-loop implementation is killed by the subprocess timeout and never
  binds. Crashing implementations are subprocess-isolated (hard rule: untrusted code
  never runs in-process).
- **Store:** content-addressed .sigil/ (objects, goals registry, bindings, verdict
  cache), relocatable, sticky 4->8 display escalation persisted in config (D-018).
- **Verdicts:** pass/fail cached forever; timeout/error transient (D-019). Binding only
  on pass; 'provisional' visible in describe_goal() sheet lines.
- **CLI:** sigil verify <#goal-hash> --store --inputs --timeout --json live;
  sigil build gained --store (registers module/goal/fn objects + goal index).
- **Next phase:** 4 — MCP harness (sheet/expand/patch/verify/lift tools, R1-R3).
  Consult sigil-harness-rules + the mcp-builder skill BEFORE starting (CLAUDE.md).
- Decisions through D-020 logged.


## Session 2026-06-12 (end)

- **Phase 2 complete** (language + transpiler) — exit gate green.
- **Suite:** 87 tests passing; ruff check + format clean.
- **Order of work followed** (sigil-transpile-verify skill): docs/grammar.md written
  first (LL(1), glyph/ASCII alias table), round-trip properties failing-first, then
  lexer/parser/printer, then transpiler + static effect check.
- **Round-trip gates:** print(parse(text)) == text on the canonical corpus;
  parse(print(ast)) == ast over 150 hypothesis-generated modules. Property testing
  caught a real grammar ambiguity -> newline-terminated statements (D-014).
- **Phase 2 exit gate:** examples/new-module — fetch_prices written in Sigil,
  transpiled, runs against a mocked API with verify clauses passing; over_budget.sg
  rejected at build time with the golden chain message
  ("fetch_prices -> save_cache: open requires !fs; budget allows !net(api.example.com)").
- **Contracts:** pre/post -> assertions gated by __sigil_contracts__; SIGIL_RELEASE=1
  strips them; post binds the result via __<name>_impl wrapper. Goals -> generated
  test_<goal>.py with run_verify() (inputs fixture, D-013).
- **One analyzer, two callers:** lift/effects.py gained provenance (FnFacts.reasons)
  and now backs both the lifter rows and transpile/effectcheck.py chains.
- **CLI:** sigil build live (--out, --json); lift unchanged; verify/serve still stubs.
- **Next phase:** 3 — verify runner + store (.sigil/ objects, subprocess isolation,
  (goal_hash, impl_hash) cache, <50ms cache-hit gate). Consult sigil-transpile-verify
  skill section on the verify runner before starting.
- Decisions through D-017 logged.


## Session 2026-06-11 (end)

- **Phases complete:** 0 (core AST + hashing) and 1 (lifter Tiers 1–2) — exit gates green.
- **Suite:** 64 tests passing; ruff check + format clean; CI matrix (3.11/3.12) committed.
- **Phase 0 gate:** hypothesis property tests — formatting/comment/docstring noise never
  moves a hash; semantic mutations always do; CBOR round-trip byte-identical.
- **Phase 1 gate:** requests 2.34.2 (6,385 lines) lifted -> 302-entry digest sheet
  (golden, verbatim); 31-fixture effect benchmark, zero under-reports, 2.9% over-report;
  hand-labeled 30-function OSS spot-check: 6.7% under-reporting before fixes (<10% gate),
  one miss fixed via fixture case_031, one documented (D-008).
  Spot-check record: tests/fixtures/oss/spotcheck-2026-06-11.md.
- **The PoC's known Path/!fs miss is fixture #1 and passes.**
- **Blockers:** none. Sandbox env notes: Python 3.10 runtime (D-001); run tests with
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/tmp/pyc PYTHONPATH=src (mount serves
  stale .pyc otherwise).
- **Next phase:** 2 — language + transpiler. Write docs/grammar.md FIRST, then
  parser/printer round-trip property tests, then implementation
  (consult .claude/skills/sigil-transpile-verify before starting).
- Decisions D-001…D-010 logged in docs/decisions.md; limitations.md seeded.
