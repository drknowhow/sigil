# Roadmap — post-1.0 (triaged from firstuse/UPGRADE_PROPOSALS.md)

**Status 2026-06-12: items 1–11 SHIPPED (v1.1.0, v1.2.0, v2.0.0 — see CHANGELOG).
Remaining: JVM/JS frontends (v3, per the proposal's own ordering).**

Disposition argument: firstuse/PROPOSALS_RESPONSE.md. Ordering rule inherited
from the v1 plan: depth before width; never cut tests; the harness stays the
product.

## v1.1 — "would actually adopt" (Python depth)

1. **Effect modes + module budgets** — `!fs.read(path)` / `!fs.write(path)` /
   `!db`, explicit denials, and a module-level `fx:` budget every fn must
   satisfy. Mode-uncertain calls keep `?`. Extends, never replaces, the
   existing row machinery. (P0.1, modified surface)
2. **`@sigil.bind` decorator** — Python-native entry point; decorator is a
   lifter frontend over the existing canonicalizer/store/runner. (P0.2)
3. **Patch-by-snippet** — send replacement source; Sigil tree-diffs canonical
   forms and emits minimal ops. Canonical paths stay as the compiled form.
   (P1.5, snippet variant)
4. **`sigil unbind` tombstones** + **sheet diff view**. (P3.10, P3.8)

## v1.2 — close the loop

5. **Recorded inputs per goal** (repo-committed `<goal>.inputs.json>`) —
   prerequisite for 6 and 7; revisits D-020 deliberately.
6. **`sigil check --against <ref>`** — CI regression gate; re-verifies at
   HEAD every goal bound at base; tombstoned goals exempt. (P1.4)
7. **`sigil watch`** — stdlib polling daemon: save → re-lift → re-verify
   touched goals. (P1.3)
8. **Property generation from typed contracts** — hypothesis-backed; only
   for fully-typed goals; counterexamples append to recorded inputs. (P2.7)

## v2 — width

9. **Language-neutral IR (S1)** — one-way door: lands complete in one major
   version with a store migration tool (every hash changes; re-lift detects,
   D-002). Prereq for any second language.
10. **R frontend (S2)** — reproducibility wedge (`analyze(seed=42) ≡ #hash`).
    Tier 1 + result-hash contracts first; Tier-2 effect inference in R is
    explicitly hard (NSE, promises, library() side effects) — `!unsafe?`
    early and often.
11. **Tier-3 contract proposer** (deferred from v1.0, D-026) + the narrow
    pytest bridge (parametrize tables only). (P2.6)
12. **Multi-fn invariants** (P3.9); JVM/JS frontends per the proposal's own
    ordering.

## Explicitly rejected

- Selector-grammar patch DSL (subsumed by patch-by-snippet).
- Proof-language ambitions; Rust/C++ frontends (build-step latency kills the
  loop UX). Both per the proposal's own "skip" list, seconded.
