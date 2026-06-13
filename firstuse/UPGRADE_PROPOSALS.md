# Sigil — Upgrade Proposals

From the same first user (Yep / Tess session, 2026-06-12). Companion to
`FIRST_USE_REPORT.md`. Ranked by leverage-for-real-agent-work, not by
implementation cost. Each item is an opinion, not a spec — push back hard.

---

## P0 — The unit is too small

### 1. Effect-typed module contracts

**The problem.** Today a goal binds one function. Real agent work happens at
the module / boundary level: "this function only touches table X; never
network; never the filesystem outside /tmp." The per-fn contract is too
fine-grained to displace pytest for anything beyond a pure helper.

**The hint already in the codebase.** Effect inference flagged
`load_config` as `!fs !unsafe?` during my first-use run. That's the seed
of the bigger idea — the inference is there; the **declarable surface
isn't**.

**Proposal.** Let a sigil contract assert effects at module boundary:

    goal load_config:
        effects: { fs: read-only, net: none, db: none }

Verify-on-patch then catches any new `import requests`, `open(..., 'w')`,
or sqlite call inside the bound module — not just wrong return values.
This is what would actually move me to reach for Sigil over `pytest +
mypy --strict`.

### 2. Familiar surface — decorate, don't translate

**The problem.** The `.sg` mini-language is the highest adoption tax.
Lift/expand/canonical-path is impressive engineering, but for someone
working in a Python codebase, the cognitive load of "this is Python but
also not" is a barrier. The patch-path schema (`body.stmts.0.value.right.val`)
is the symptom.

**Proposal.** Provide a `@sigil.bind(goal=...)` decorator that wraps an
ordinary Python function. Sigil lifts on import, store-hashes the AST as
today, verifies via the same runner. The user writes Python; Sigil sees
content-addressed Sigil. The `.sg` surface stays for advanced cases
(formal proofs, multi-binding) but isn't the entry point.

This is the single biggest thing that would change "I'd watch this" to
"I'd use this in Yep tomorrow."

---

## P1 — Close the loop end-to-end

### 3. Watch mode — `sigil watch`

**The problem.** Verify-on-patch is the headline win, but I have to
remember to issue the patch. In practice I edit in my IDE.

**Proposal.** A `sigil watch <path>` daemon: file save → re-lift → verify
every bound goal touching that file → toast/exit-code on regression.
This converts Sigil from "I run a tool" to "the seatbelt is always on."

### 4. CI gate — `sigil check`

**The problem.** Bind state lives in the local store. Nothing today
stops me from pushing code where a previously-bound goal now fails.

**Proposal.** `sigil check --against=origin/main` — fails non-zero if
any goal that was bound at the base SHA is unbound at HEAD. One line in
GitHub Actions. This is the move that gets Sigil into team workflows.

### 5. Patch-path selector DSL

**The problem.** Canonical paths (`body.stmts.0.value.right.val:=3`) are
fragile and AI-unfriendly. `expand(canonical)` helps a human read them;
neither a human nor an LLM authors them comfortably.

**Proposal.** A selector grammar that targets by **semantics**, not
position:

    patch:
        select: "return expression > right operand > literal"
        set: 3

Or, more aggressively: accept a small Python snippet showing the
intended replacement and let Sigil compute the path. Patch is the
most-used verb and currently the highest-friction one.

---

## P2 — Adoption ramp

### 6. Pytest bridge — `sigil from_pytest`

**The problem.** Every Python repo has pytest. Asking them to rewrite
tests as goals is a non-starter.

**Proposal.** `sigil from_pytest tests/` reads pytest parametrize
fixtures + assertions, generates corresponding `goal X: forall inputs:
assert Y` entries, and binds them to the functions under test. Now
existing tests are content-addressed for free; new contracts are
incremental, not a rewrite.

### 7. Property-based generation from goals

**The problem.** Once a goal exists, Sigil only checks the examples the
user supplied. Hypothesis-style property fuzzing inside the contract is
a natural extension that pytest cannot match.

**Proposal.** For numeric / typed contracts, auto-generate N random
inputs satisfying the precondition; assert the post. Counterexamples
get appended to the sheet as new permanent test cases. This is the
"why would I use Sigil over pytest" answer for a math-heavy library.

---

## P3 — Surface polish (small wins)

### 8. Sheet diff view

Two sheets, two commits: show which goals went from bound → unbound,
new goals, dropped goals. Lets a reviewer skim a PR's contract impact.

### 9. Multi-fn invariants

`invariant: forall x: round_trip(serialize, deserialize, x) == x`.
Binds a property to **two** functions; either patching breaks it.

### 10. `unbind` as a first-class verb

Today the sheet is append-only, which is correct. But there's no
ceremony for "I deliberately retired this contract." A `sigil unbind
<goal>` that writes a tombstone (signed, dated, reason) keeps the
ledger honest without forcing the goal to live as a permanent failure.

---

## P-Strategic — Language-agnostic architecture

**Revised from the earlier "stay deep in Python" stance.** On reflection,
the core idea (content-addressed goal/fn store + verify-on-patch +
append-only sheet) is genuinely language-neutral. What's Python-specific
in 1.0.1 is the *implementation*, not the *model*. Done right, going
multi-language is not scope creep — it's the move that turns Sigil from
"a Python verification tool" into "the substrate for verified
agent-driven coding, everywhere."

### Why this matters now

Three forces converge:

1. **Agents are language-promiscuous.** I write Python in Yep, but the
   same agent loop happens in JS for web work, Java for enterprise
   backends, R for stats/scientific computing, Go for infra. A
   verification substrate that only covers one language locks Sigil out
   of all the other agent surfaces.
2. **Scientific reproducibility is a real wedge.** R and Julia
   workflows have a brutal reproducibility problem — "this analysis
   returned X last week, Y this week, nobody knows why." A content-
   addressed contract that says `analyze(seed=42) ≡ #abcd1234` is
   genuinely novel value there. Pytest doesn't cover this.
3. **Java/Kotlin enterprise CI is exactly where `sigil check` belongs.**
   The market that pays for verification tooling is enterprise JVM.
   Python-first is the right v1 wedge; JVM is where the money is.

### The architectural shift

Three layers, cleanly separated:

| Layer | Today (1.0.1) | Proposed |
|---|---|---|
| **IR** | Python-AST tuple form | Language-neutral S-expression IR with effect annotations |
| **Lifters** | Python AST → IR (one impl) | Per-language frontends: Python, R, Java, JS, Go |
| **Verify runner** | Python subprocess | Per-language runner pool (rscript, java, node, go run) |
| **Sheet/store** | Already language-neutral ✓ | Unchanged |

The content-addressed store and sheet are **already** language-neutral
— hashes don't care what AST shape they came from. The work is in the
lift + verify layers, and it's parallelizable across languages.

### Concrete proposals

#### S1. Language-neutral IR

Define Sigil's canonical form as a tagged S-expression with effect
annotations, not Python AST tuples. Each language frontend lifts to
this. Patch paths target the IR, not the source AST — so they're
stable across languages and across language-version upgrades.

#### S2. R frontend — the scientific wedge

R is the highest-leverage second language. Reasons:

- **Reproducibility crisis is real and acknowledged.** Bioconductor,
  CRAN, academic stats workflows all suffer from "the function changed
  upstream and my paper's number drifted."
- **Functional-ish surface.** R functions are first-class, mostly pure
  in idiomatic use, easy to lift.
- **No incumbent.** Nothing in the R ecosystem does content-addressed
  verify-on-patch. `testthat` is pytest's cousin; `renv` does deps;
  neither does contracts.
- **Adjacent to MSD work.** Dimitri's R&D context (immunoassay/life
  sciences) is exactly where this wedge applies — assay analysis
  pipelines are the canonical "this number must be reproducible" case.

R also has a clean AST (`base::quote`, `pryr`, `rlang::expr`) that's
easier to lift than Python's positional/keyword chaos.

#### S3. Java/Kotlin frontend — the enterprise CI play

- **Eclipse JDT** or **JavaParser** give a stable AST.
- Java method signatures are already typed, so effect annotations
  partially infer themselves.
- The `@sigil.bind` decorator (P0 #2) becomes a Java annotation:
  `@SigilBind(goal = "...")`.
- `sigil check --against=origin/main` in a Gradle/Maven CI is the
  shape enterprise pays for.

#### S4. JS/TS frontend — covers web agent work

Babel AST → IR. The interesting wrinkle: TS type contracts can be
lifted INTO Sigil goals automatically. "Function signature says
`(x: number) => string`" becomes a free precondition.

#### S5. Go frontend — covers infra agent work

Go's `go/ast` package is the cleanest AST in any mainstream language.
Effect inference is partial — Go's net/io packages are easy to detect.

### The honest trade-off

Going multi-language has costs:

- **Surface area explosion.** Five lifters × five verify runners ×
  per-language idiosyncrasies = a lot more code to maintain than one
  good Python implementation.
- **Dilutes Python depth.** If P0/P1 (effect-typed module contracts,
  `@sigil.bind`, `sigil check`) aren't done first, multi-language just
  spreads the per-language shallowness.
- **Effect inference doesn't generalize cleanly.** Python's `import`
  graph, R's `library()`, Java's classpath, Go's package imports — each
  has its own model of "what's a side effect." The language-neutral
  IR has to be carefully designed to expose this without leaking.

### Recommended order

1. **First**: finish the P0/P1 items on Python. Don't expand width
   until the Python depth is real. A Python-only Sigil that nails
   effect contracts + `@sigil.bind` + CI gate is more valuable than a
   five-language Sigil where none of them have those.
2. **Then**: R frontend as a focused 2.0. Scientific reproducibility
   wedge, narrow user base, validates the language-neutral IR.
3. **Then**: Java + JS in parallel as 3.0. Enterprise CI and
   web-agent coverage.
4. **Go**: opportunistic, lowest priority. The infra-agent market is
   smaller and overlaps with existing Go tooling.

---

## What I'd still skip

- **Proof-language ambitions.** Coq/Lean/F*/Dafny are the prior art
  here. Sigil's wedge is "agent-driven verify loop," not "machine-
  checked theorems." Don't drift.
- **Compiled languages with heavy build steps as v2.** Rust and C++
  have AST tooling (rust-analyzer, clang-tidy) but the lift-verify
  loop becomes minutes, not seconds. The headline UX dies. Defer.

---

## The one-line summary

**Today, Sigil is a research-grade per-function Python verifier. The
shortest path to a tool I'd actually adopt is: (a) effect-typed
module contracts, (b) `@sigil.bind` over a `.sg` rewrite, (c)
`sigil check` in CI — all on Python first. THEN multi-language
(R for scientific reproducibility, Java for enterprise CI) turns it
into a substrate, not a tool.**

— Yep / Tess, 2026-06-12 (rev. 2)
