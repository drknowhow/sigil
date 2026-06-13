# Response to UPGRADE_PROPOSALS.md — review with pushback, as invited

Verdicts: **accept** / **accept-modified** / **defer** / **reject**. The triaged
plan lives in `docs/roadmap-next.md`; this file is the argument.

---

## P0.1 Effect-typed module contracts — **accept-modified** (v1.1, top of list)

Agreed this is the highest-leverage item, and you found the right seam: the
inference exists, the declarable surface doesn't. Two modifications:

- **Surface**: not the YAML-ish `effects: {fs: read-only}` — it conflicts with
  the LL(1) grammar for zero gain. The semantics land in the existing effect
  row: mode-qualified effects (`!fs.read(./config)`, `!net.none` as explicit
  denial) plus a module-level `fx:` budget block that every fn in the module
  must satisfy. Same meaning, one grammar.
- **Honesty constraint**: read/write mode inference is statically decidable
  for the common cases (open modes, read_text vs write_text, requests.get vs
  post) but not in general — mode-uncertain calls get `!fs.write?` (the `?`
  convention extends, never silences). `db:` becomes a first-class effect
  (sqlite3/DB-API rules already half-exist in the rule table).

This is also the item that finally makes D-015 (scopes carried, not enforced)
partially obsolete — in the right direction.

## P0.2 `@sigil.bind` decorator — **accept** (v1.1, ships with P0.1)

Correct, and the sharpest adoption observation in the doc. One reframe: this
isn't "decorate instead of translate" — the decorator IS a lifter frontend.
The user writes Python; on import, Sigil lifts the function through the same
canonicalizer, hashes it, binds against the named goal, and the verify runner
is unchanged. `.sg` remains the canonical store form; nothing forks.
`@sigil.bind(goal="dedupe")` for store goals; `@sigil.bind(verify=["out.set ==
xs.set", "out.len == out.set.len"], inputs="tests/dedupe_inputs.json")` for
inline ones (clauses parse with the existing expression parser).

## P1.3 `sigil watch` — **accept** (v1.2)

Agreed on "seatbelt always on." Stdlib polling watcher (no new dependency),
re-lift on mtime change (re-lift is already idempotent and cheap), re-verify
touched bound goals. After P0.2, because watch without bind reaches almost
nothing.

## P1.4 `sigil check` CI gate — **accept-modified** (v1.2, with a named prerequisite)

Right target, and yes, this is what gets Sigil into team workflows. The
pushback: it's not "one line in GitHub Actions" yet, because **verify inputs
are caller-provided (D-020) and the store is local/gitignored**. CI can't
invent inputs. Prerequisite shipped first: goals get *recorded inputs* — a
repo-committed `<goal>.inputs.json` referenced from the goal (this also
unblocks your P2.7). Then `sigil check --against <ref>`: enumerate goals bound
at base, re-verify at HEAD, fail on regression. The store stays local; check
re-derives, never trusts a committed bind state (committed verdicts would be
trivially forgeable — the whole point is re-verification).

## P1.5 Patch selector DSL — **accept the snippet, reject the DSL** (v1.1)

The selector grammar is a second language to learn with its own ambiguity
problems ("return expression > right operand" breaks on the second return).
Your "more aggressive" variant is strictly better and you should have led
with it: **patch-by-snippet**. Send the replacement source for the function;
Sigil canonicalizes both sides, tree-diffs them, and emits the minimal ops
itself. Untouched subtrees stay untouched by construction — same guarantee,
zero path authoring. Canonical paths remain as the low-level form (and what
snippet-diff compiles to).

## P2.6 pytest bridge — **defer** (v2 candidate)

The honest problem: extracting intent from arbitrary pytest assertions is
Tier-3 territory — heuristic, untrusted-until-verified. A narrow version
(parametrize tables → input/expected pairs → goals) is tractable; the general
version silently launders test code into specs. Deferred until the Tier-3
proposer exists, where it belongs.

## P2.7 property-based generation — **accept-modified** (v1.2)

hypothesis is already a dev dependency and typed params (Int, Str, [Int]) give
us generators for free. Two constraints: only when the goal's types are fully
known (no guessing generators), and counterexamples append to the recorded
inputs file — which makes them *permanent regression cases*, the best part of
your proposal. Depends on P1.4's recorded-inputs prerequisite.

## P3.8 sheet diff — **accept** (v1.1, small)
## P3.10 `unbind` tombstone — **accept** (v1.1, small)

Both philosophically consistent: append-only ledger + explicit ceremony.
Tombstone = dated, reasoned entry in the store index + a sheet line; the goal
stops counting as a regression in `sigil check`.

## P3.9 multi-fn invariants — **defer** (v2)

Real value, real grammar/runner surface. After the IR question settles —
invariants over two functions are exactly where a hasty design calcifies.

---

## P-Strategic: multi-language — **agree with your own ordering; two corrections**

Your "recommended order" (Python depth first, then R, then JVM/JS) is right
and we'll hold you to it. Corrections to the supporting claims:

1. **"R has a clean AST … easier to lift than Python" — overstated.** R's
   *parse tree* is clean; R's *semantics* are not: non-standard evaluation,
   promises/lazy args, `library()` side effects at any scope, and
   `eval(parse(text=…))` as an idiom. Tier-1 lifting R is easy; Tier-2 effect
   inference in R is *harder* than Python, not easier. The reproducibility
   wedge survives this (hash-bound results don't need full effect inference),
   but plan it eyes-open.
2. **The IR migration cost is missing from the trade-offs.** Hashes are
   forever (verdict cache, bindings, sheets). Re-basing the canonical form
   onto a language-neutral IR changes every hash in every store. That's not
   fatal — re-lift detects changed hashes by design (D-002) — but it means S1
   is a one-way door that must land *complete* in a single major version,
   with a store migration tool. This is the strongest reason to do exactly
   what you propose: Python depth first, IR second, never iteratively.

Also seconded: skipping proof-language ambitions and heavy-build compiled
languages. That instinct matches the roadmap's founding constraint ("the
fatal mistake would be building a runtime").

---

**Bottom line accepted as stated**: (a) effect-typed module contracts,
(b) `@sigil.bind`, (c) `sigil check` — Python first, in that order, with
recorded-inputs as the unlisted prerequisite that makes (c) and P2.7 real.
