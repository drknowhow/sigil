---
name: sigil-transpile-verify
description: Rules for the Sigil text projection (parser/printer), the Sigil-to-Python transpiler, the static effect-budget check, and the verify runner. ALWAYS consult before writing or modifying anything in src/sigil/lang/, src/sigil/transpile/, or src/sigil/verify/, before editing docs/grammar.md, and whenever a round-trip, transpilation, or contract-execution test fails.
---

# Sigil Projection, Transpiler & Verify Runner

## Order of work (Phases 2-3, do not reorder)
1. Write `docs/grammar.md` FIRST — full grammar, LL(1), no ambiguity. Every production decidable on one token of lookahead; if a construct needs more, redesign the construct.
2. Parser + printer, with both round-trip properties as failing tests before implementation:
   `print(parse(text)) == text` (for canonical text) and `parse(print(ast)) == ast` (always).
3. Transpiler. 4. Verify runner.

## Projection rules
- The AST is the source of truth; text is a projection. The printer defines canonical text — one true formatting, no options in v1.0.
- Glyphs each have exactly one ASCII alias (AND-glyph/and, subseq-glyph/subseq_of, <=, ->). Parser accepts both; printer emits glyphs. The alias table lives in grammar.md.

## Transpilation mapping (Sigil -> Python)
| Sigil | Python |
|---|---|
| fn + body | def with type hints |
| pre/post contracts | assertions gated by `if __sigil_contracts__:` (stripped when SIGIL_RELEASE=1) |
| post with result binding | inner wrapper capturing the return value |
| goal block | generated `test_<goal>.py` module running verify clauses |
| effect rows | NO runtime artifact — enforced statically (below) |
| !unsafe | requires an `ack:` reason string in the goal, else build error |

## Static effect check (transpile/effectcheck.py)
- Build the call graph of the module + lifted dependencies; compute each fn's row by reusing lift/effects.py fixpoint — ONE implementation, two callers.
- A goal's `fx:` line is a budget: implementation row must be a subset of the budget or the build fails.
- The error message names the violating *call chain*: `fetch_prices -> _save -> Path.write_text requires !fs(./cache); goal budget: !net`. This message has a golden test.

## Verify runner
- Subprocess execution: timeout (10s default, per-goal override), stdout/stderr captured and returned on failure only.
- Cache key (goal_hash, impl_hash) -> verdict; content-addressed, never expires (hashes are immutable). Cache hit must be <50ms (gate test).
- A passing verify binds goal<->impl in the store; failing or timed-out never binds. `provisional` is the only state for unverified bindings and must be visible in every sheet line that includes one.
