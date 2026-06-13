# Changelog

## v2.0.1 — 2026-06-13 (second field report fixes)

- **Fixed: Windows/encoding crash** (V2_REPORT Bug 2). CLI pins stdout/stderr to UTF-8;
  all capture_output subprocesses decode UTF-8 with `errors="replace"`; the sheet footer
  is ASCII. A stock cp1252 console no longer crashes `sigil lift` on its own glyphs.
- **Fixed: invariant binding not persisted after a patch** (Bug 1). `patch`/`patch_snippet`
  now re-register + bind an invariant against the patched module on pass, so a later
  `verify_invariant` agrees with the patch verdict (was contradictory).
- `from-pytest` derives the expected column from the assert RHS (a `"n,exp"` table used to
  extract nothing); `sigil migrate` accepts `--store`; rejected Tier-3 proposals get a
  distinct sheet status line.
- CI: added Windows (3.12) and Ubuntu 3.13 lanes. Version-sensitive lift goldens record
  their generating Python minor and assert byte-exact only there, structure-only off it
  (operationalizes D-002 — the 3.14 AST drift the report saw is expected, not a defect).

## v2.0.0 — 2026-06-12 (width: roadmap-next wave 3 — Sigil as substrate)

- **Language-neutral IR (S1)** — lifted code now hashes to a tagged neutral IR
  instead of Python-AST tuples; patch paths and expand operate on it; exotic
  constructs host-wrap honestly instead of crashing. The one-way door, softened:
  pre-IR store objects remain readable forever; `sigil migrate` surveys a store
  and bumps its format (D-036). Lifted digests changed once; goldens regenerated.
- **R frontend (S2)** — `sigil lift script.R`: tokenizer-canonical Tier-1
  hashing (comments/whitespace never move a hash) + token-rule effect rows;
  `library()`/`source()`/`do.call` earn `!unsafe?` early and often, as promised.
  `sigil check-r --fn analyze --args "[42]" --expect #hash`: result-hash
  reproducibility contracts (needs Rscript; lifting doesn't).
- **Multi-fn invariants (P3.9)** — `invariant round_trip { over: enc, dec
  verify: dec(enc(x)) == x }`; patching either fn re-verifies automatically;
  passing binds the invariant to all impl hashes.
- **Tier-3 propose/validate** — `propose_contract` MCP tool: the connected
  agent IS the proposer; proposals register provisional and can only bind by
  passing verification. `sigil from-pytest` extracts parametrize tables into
  reviewable goal DRAFTS (never auto-registered).
- JVM/JS frontends deferred to v3 per the proposal's own ordering.

## v1.2.0 — 2026-06-12 (close the loop: roadmap-next wave 2)

- **Recorded inputs** (prerequisite, D-020 revisited): goals carry
  `inputs: "file.json"`, `@sigil.bind(inputs=...)` records inline; the runner
  resolves them when the caller passes none. Verdict cache key now includes
  the inputs digest.
- **`sigil check [paths] [--against REF]`** (P1.4): rebuilds every .sg,
  re-verifies every goal with recorded inputs; with --against also fails on
  contracts dropped since the base ref without a tombstone. Exit 1 on any
  regression — one line in CI.
- **`sigil watch`** (P1.3): stdlib polling daemon — save → rebuild/relint →
  re-verify touched goals; Python files are checked against `__sigil_fx__`.
- **Property generation** (P2.7 modified): deterministic typed-contract input
  generation (`run_property_check`, `sigil verify --gen N`); counterexamples
  append to the store permanently and become the recorded input when none
  exists.
- Verify harness evaluates many cases per subprocess; crashing implementations
  now return structured `fail` with the exception as clause detail.

## v1.1.0 — 2026-06-12 (depth: roadmap-next wave 1)

- **Effect modes + module budgets** (P0.1): `!fs.read(path)` / `!fs.write`,
  first-class `!db`; `open()` literal-mode detection; read+write collapse to
  unmoded supersets (never under-report); module-wide `fx:` budgets in .sg and
  `__sigil_fx__ = "..."` in Python, enforced over every fn's reachable row.
  Budget errors are mode-precise.
- **`@sigil.bind`** (P0.2): Python-native lifter frontend — registers goal +
  impl + module snapshot on import; declared fx checked statically at import;
  verification stays subprocess-isolated and never runs at import.
- **Patch-by-snippet** (P1.5): send the corrected definition; Sigil tree-diffs
  canonical forms into minimal ops (snippet ≡ re-lift, by hash). MCP tool
  `patch_snippet`; selector DSL rejected per PROPOSALS_RESPONSE.md.
- **`sigil unbind`** tombstones (dated, reasoned) + **`sigil diff`** store
  contract-impact view (P3.10, P3.8).
- Node shapes extended once for the whole roadmap (Effect.mode, Module.fx,
  Goal.inputs_ref): store object hashes change — re-run `build --store`/re-lift
  (D-034). Goldens regenerated.

## v1.0.1 — 2026-06-12 (first-use report fixes)

External first-use report (firstuse/FIRST_USE_REPORT.md) drove this release:

- **Fixed: served `verify` deadlock.** The verify subprocess inherited the MCP
  server's stdin — the client's JSON-RPC pipe — hanging every verify under
  `sigil serve` (and letting untrusted code read client traffic). Now
  `stdin=DEVNULL`; regression-tested through a real stdio ClientSession.
- **Goals are reachable over pure MCP**: new `load_module(source)` tool; a
  session over an existing store starts with registered goals on the sheet.
- `expand(hash, form="canonical")` exposes the patch-path schema; the
  agent-workflow skill documents the real lifted-Python path shape
  (`body.data.…`).
- `patch` returns the sheet display hash alongside the full hash; transpiler
  scaffolding (`__sigil_*`) no longer appears on digest sheets.
- **Distribution renamed `sigil-lang`** — "sigil" is a taken PyPI name and a
  pre-existing install shadowed ours during testing. Import and CLI remain
  `sigil`.

## v1.0.0 — 2026-06-12

First production release. Highlights:

- **Core**: canonical AST (35 node kinds incl. expression language), canonical
  CBOR + sha256 content addressing; formatting/comments/docstrings never move
  a hash, semantic changes always do (hypothesis-verified).
- **Lifter (Tiers 1–2)**: full-module lifting (functions, classes-as-records,
  imports); effect inference with origin tracking through assignments,
  annotations, `with`, call results and helper returns; call-graph fixpoint;
  `!unsafe?` honesty for dynamics. 33-fixture benchmark: zero under-reports.
- **Language + transpiler**: LL(1) text projection (docs/grammar.md) with
  lossless round-trip; contracts -> env-gated assertions; goals -> generated
  test modules; static effect budgets with call-chain errors.
- **Verify runner + store**: subprocess-isolated, timeout-guarded verification
  cached by (goal, impl) hash (<50ms hits); relocatable `.sigil/` store;
  binding only on pass; `provisional` everywhere else.
- **MCP harness** (`sigil serve`): lift/sheet/expand/patch/verify under
  R1 (append-only context, property-tested), R2 (expand-over-regenerate),
  R3 (auto-verify, patch-the-subtree feedback).
- **Measured cost model** (docs/cost-model.md): real-tokenizer numbers,
  including an honest correction of the spec's first-contact claims
  (5.9x on requests 2.34.2, not "10x+"; the larger wins are per-iteration).

Cut from v1.0 (plan §11 allowed cuts): Tier-3 contract proposer.
