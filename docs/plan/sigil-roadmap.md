# SIGIL — Functionality & Lifter Roadmap

*Companion to spec v2.1. Two questions answered: how Sigil runs real programs, and how existing code gets into Sigil.*

## Part 1 — Making it functional

The fatal mistake would be building a runtime. New-language graveyards are full of projects that spent three years on a VM before anyone ran a program. Sigil's value is the *representation* — goals, contracts, effects, hashes — not novel execution semantics. So it borrows execution:

**Phase A — Sigil as a front-end (transpile to host).** The projection compiles to plain Python (later TypeScript). Functions become functions; contracts become runtime assertions in dev builds and disappear in release; `goal` blocks become test modules that run the `verify` clauses; effect rows are checked **statically at transpile time** — the transpiler walks the call graph and rejects any implementation exceeding its goal's effect budget. Nothing about effects needs runtime machinery; it's a graph check.

This means on day one a Sigil program runs anywhere Python runs, uses any Python library (declared as effect-bearing imports), and debugs with normal tooling. The host language is an implementation detail, the way C was for early C++.

**Phase B — Pure-core interpreter.** One thing transpilation can't give: *deterministic, sandboxed verification*. Running `verify` clauses through the host runtime means trusting the host environment. A small interpreter for the pure fragment (no effects by construction) makes contract evaluation hermetic and hashable — same inputs, same verdict, cacheable by `(goal_hash, impl_hash)` forever. This is maybe 3–4k lines and only has to cover the pure core.

**Phase C — Optional native path.** Only if the project earns it. Likely never necessary; "Sigil semantics, host execution" is a stable end state.

## Part 2 — The lifter (converting existing languages to Sigil)

### Does anything like this exist?

No. Adjacent prior art: tree-sitter (uniform parsing of ~100 languages), Unison (content-addressed code, but you write Unison — it doesn't ingest Python), decompilers (lift binaries to structure, never to intent), and LLM code translation (intent-capable, correctness-blind). The composition — mechanical structure lifting + probabilistic intent lifting, with verification deciding what's trusted — is unbuilt. That's the gap.

### Why "perfect conversion" is impossible, and why that's fine

Rice's theorem: every non-trivial semantic property of a program is undecidable in general. Effects, contracts, and intent cannot be *perfectly* extracted from arbitrary source. The lifter therefore works in three trust tiers, and the architecture exists to keep them separate:

| Tier | What | Method | Trust |
|---|---|---|---|
| 1 | Structure: AST, signatures, call graph, digests | deterministic parsing + hashing | total |
| 2 | Effects: !net/!fs/!rand/!clock/!env per function | static over-approximation + optional dynamic tracing | sound-ish: may over-report, shouldn't under-report |
| 3 | Intent & contracts: goal blocks, verify clauses | LLM-proposed from code/types/docstrings/tests | **untrusted until verified** — proposed contracts run against the existing test suite and recorded I/O before binding |

Tier 3 is the honest crux: a lifted contract is a *hypothesis about what the code means*. The harness promotes it to a binding spec only when it passes against observed behavior — and flags it `provisional` otherwise. A lifter that skipped this step would silently launder LLM guesses into specs.

### Architecture

```
source repo
   │  tree-sitter / native ast (per-language frontend)
   ▼
Sigil core AST  ──────────────►  digest sheet (#hash lines)        [Tier 1]
   │
   ├─ effect walker (call-graph rules + import map)                [Tier 2]
   ├─ contract proposer (LLM: types/docstrings/tests → verify)     [Tier 3]
   │      └─ validator: run proposals vs test suite + traces
   ▼
Sigil module: goals (provisional|verified) + impls + dictionary
   ▼
MCP harness: digest / expand / patch / verify   (R1–R3 from v2.1)
```

The frontend is per-language; everything after the core AST is language-agnostic. Python first (richest `ast` module, your stack), TypeScript second, R third — R is realistic precisely because the lifter only needs Tier 1+2 to be useful.

### What lifted code is immediately good for

Even before any Tier 3 contract exists, a lifted repo gives you: the digest sheet (90% context reduction), AST patches (cheap edits), the project dictionary, and effect budgets (catch the AI adding I/O). That is — the entire v2/v2.1 efficiency story works on *legacy code* with only the mechanical tiers. Contracts arrive incrementally, function by function, where they pay.

### Phased plan

1. **Weeks 1–2 — Tier 1 for Python.** `ast` → canonical form (strip docstrings/comments, normalize) → sha-digest → digest-sheet emitter. Exit: any Python repo → one-page digest sheet, round-trip stable. *(A seed of this exists — see `sigil_lift.py` beside this doc.)*
2. **Weeks 3–4 — Effect walker.** Import-rooted rules (requests→!net, open/pathlib→!fs, random→!rand, datetime.now→!clock, os.environ→!env) propagated over the call graph; unknown calls → `!unsafe?` rather than silence. Exit: effect rows on a real repo with <10% manual corrections.
3. **Weeks 5–7 — MCP harness.** digest / expand(#hash) / patch / verify tools, append-only context assembly (R1), patch-based repair loop (R3). This is the piece that overlaps C3 most heavily — same problem, stricter substrate. Exit: a Claude Code session edits a lifted repo through patches only.
4. **Weeks 8–10 — Transpiler (Phase A).** Sigil projection → Python with contract assertions and static effect check. Exit: write a new module in Sigil, run it, watch an over-budget effect get rejected at compile time.
5. **Weeks 11–14 — Tier 3 contract proposer.** LLM proposes verify clauses; validator runs them against pytest + recorded traces; `provisional`/`verified` status tracked per goal. Exit: ≥60% of proposed contracts on a mid-size repo validate without human edits, zero unverified contracts presented as specs.
6. **Later — pure-core interpreter (Phase B), TS/R frontends, dictionary learning.**

### Honest risk register

- **Effect inference in dynamic Python** (getattr, monkeypatching, eval) can defeat static walking — the design answer is the `!unsafe?` marker plus optional dynamic tracing, never false confidence.
- **Tier 3 quality is unproven.** The 60% validation target is a guess; if it lands at 20%, the lifter is still worth shipping on Tiers 1–2 alone.
- **Round-trip fidelity** (lift → edit → lower back to idiomatic Python) is genuinely hard; v1 of the lifter is one-directional plus patches, not a bidirectional sync engine.
- **Adoption physics:** a language nobody shares is a private notation. The mitigation is built into the plan — the lifter makes Sigil useful on *other people's* languages from week 2, which is the only realistic wedge a new language has in 2026.
