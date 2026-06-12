# Changelog

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
