# SIGIL — Specification v2.1

*A deterministic, intent-first language for human↔AI program construction.*

## Why another language

Natural language is optimized for ambiguity tolerance between humans. That's exactly wrong for specifying programs: "fetch the prices and cache them" has hundreds of valid implementations and no way to check which one you got. Mainstream programming languages fix ambiguity but throw away intent — the *why* lives in comments and commit messages, invisible to compilers and mostly invisible to AI assistants.

Sigil's bet: the scarce resource in AI-assisted coding is no longer typing speed, it's **specification fidelity** and **verification cost**. So the language makes intent, contracts, and effects first-class and machine-checkable, while keeping a token-dense surface syntax so it's cheap to put in an LLM context window.

## Design pillars

1. **One parse, ever.** The canonical form of a Sigil program is its AST (CBOR-encoded). The text syntax is a *projection* of the AST, not the source of truth. No grammar ambiguity, no formatting wars, no parser drift between tools.
2. **Intent is code.** Programs begin as `goal` blocks — structured intent with inputs, outputs, effects, constraints, and verification clauses. An implementation is only *accepted* if it satisfies the goal's `verify` clauses.
3. **Effects are visible.** Every function declares its effect row (`!net`, `!fs`, `!rand`, `!clock`, or `pure`). Calling an effectful function from a pure context is a compile error. An AI can't sneak in a network call you didn't ask for.
4. **Contracts over comments.** Pre/postconditions are executable. They run in dev/test, compile away in release, and serve as the oracle for AI-generated implementations.
5. **Content-addressed definitions.** Functions are identified by the hash of their AST (à la Unison). Renames are free, dependencies are exact, and "did the AI actually change the logic?" is a hash comparison.
6. **Token density.** The text projection targets ~50% fewer tokens than equivalent Python. Common patterns get single glyphs; boilerplate doesn't exist because the AST projection regenerates it.

## The goal block — the human's half

```sigil
goal fetch_prices {
  intent: "Daily OHLCV for given tickers; local cache; respect rate limits"
  in:  tickers [Str], range DateRange
  out: Frame{ticker Str, date Date, o,h,l,c F64, v U64}
  fx:  !net(alpaca.markets) !fs(./cache)
  law:
    rate <= 200/min
    cache_ttl == 24h
    retry(429) <= 3 backoff exp
  verify:
    out.rows.complete_for(tickers, range)
    out.no_nulls(o,h,l,c)
}
```

This is the entire human contribution. It is short, unambiguous, and *checkable*. An AI (or a human) produces an implementation; the toolchain runs `verify` against it. If verification passes, the implementation hash is bound to the goal hash. If the AI regenerates the implementation later, the goal doesn't move.

## The implementation — the machine's half

```sigil
fn dedupe<T: Eq+Hash>(xs [T]) -> [T]
  pure
  post |r| r.set == xs.set ∧ r.len <= xs.len ∧ r ⊑ xs   -- ⊑ = subsequence
{
  s := {}
  [x | x <- xs, s.insert(x)]
}
```

Things to notice:

- `pure` is part of the signature. Adding an `!fs` call here is a type error, not a code-review catch.
- The postcondition fully pins the semantics: same elements, no longer, order-preserving. There is exactly one observable behavior that satisfies it. The body is almost an afterthought — which is the point when an AI writes bodies.
- `∧`, `⊑`, `<-` are single tokens in the projection. The AST stores them as ordinary nodes; your editor can render them as ASCII (`and`, `subseq_of`) if you prefer. Rendering is per-user, the program is the AST.

## Effect rows

```
pure                    -- no effects
!net(host)              -- network, scoped to host
!fs(path)               -- filesystem, scoped to subtree
!rand !clock !env       -- nondeterminism sources
!unsafe                 -- escape hatch, must be ack'd at the goal level
```

Effects propagate: a function's row is the union of its callees' rows unless handled. A `goal` block's `fx:` line is a *budget* — the implementation may use at most those effects. This single rule eliminates the largest class of AI-generated-code risk (unexpected I/O) structurally rather than by review.

## What this buys you, concretely

| Problem today | Sigil mechanism |
|---|---|
| Prompt → code is unverifiable | `verify:` clauses are the acceptance test, written before generation |
| AI introduces hidden side effects | Effect rows are typed; budget enforced at the goal |
| Token cost of context | AST projection ≈ half the tokens; hashes let you reference, not re-send, unchanged code |
| Merge conflicts / refactor churn | Content addressing — renames and moves don't change identity |
| Spec drift (docs lie) | The goal *is* the spec, and it's bound to the implementation hash |

## Honest limits

- **This is a specification language with an implementation language attached, not a replacement for natural language.** Vague exploration ("what should this product even do?") still belongs in English. Sigil starts where the intent is firm enough to constrain.
- **Writing good `verify` clauses is hard** — it's the same skill as writing good tests, and underspecified verification gives AI implementations room to be technically-correct-but-wrong. The language makes the spec checkable; it can't make it complete.
- **Prior art is real**: Unison (content-addressed code), Dafny/Eiffel (contracts), Koka (effect rows), Idris (types-as-specs). Sigil's novelty is the *composition* aimed at the human↔AI division of labor, plus the AST-canonical/token-dense projection — not any single mechanism.

## v2 — The efficiency layer

v1 made programs cheap to express. v2 makes them cheap to *re-express*, which is where the real cost lives: an LLM session re-reads the same code dozens of times. Five mechanisms, ordered by payoff.

### 1. Reference, don't repeat (hash-first context)

Since every definition is content-addressed, a context window never needs the body of anything unchanged — only its **signature digest**:

```
#a3f9 dedupe<T:Eq+Hash>([T])->[T] pure |post: set-preserving subseq|
```

One line replaces the whole function. The model requests bodies on demand (`expand #a3f9`) only when it must read or modify them. A 10k-line project becomes a ~200-line digest sheet. This is the single biggest win — typically 90%+ context reduction on iteration turns.

### 2. Edits as AST patches, not re-emission

Code changes are expressed as patches against a hash, never as full files:

```
patch #a3f9 {
  at body.comprehension.guard: s.insert(x) → s.add?(x)
}
⇒ #b1c2
```

The patch *is* the diff, the review unit, and the merge unit. Output tokens scale with the size of the change, not the size of the file. (This also kills the "LLM rewrites the file and silently mangles line 340" failure mode — untouched subtrees are untouched by construction.)

### 3. Project dictionary (symbol interning)

Each project carries a dictionary mapping its recurring vocabulary — type names, hosts, paths, idioms — to short indices. The projection emits `$12` instead of `Frame{ticker Str, date Date, o,h,l,c F64, v U64}` after first use. Dictionaries are themselves content-addressed, so tools and models share one by hash. In practice this is learned per-codebase *working-set reduction*: the more internally consistent the project, the cheaper it gets. (Framing caveat, Muninn Part 2: like the digest sheet this reduces what's *carried per turn*, not the size of any single definition — and the contracts/effects deliberately *add* information. The honest token lever is content addressing → stable prompt-cache prefix + small patch deltas; see `docs/cost-model.md` and D-044 for measured numbers.)

### 4. Goal templates (the stdlib is vocabulary)

Recurring goal *shapes* collapse into parameterized templates. v1's 11-line `fetch_prices` goal becomes:

```sigil
goal fetch_prices = @cached_fetch(
  alpaca.markets → Frame[$12],
  in: tickers [Str], range DateRange;
  rate≤200/min, ttl=24h, retry(429)≤3,
  verify: complete_for(tickers,range), no_nulls(o,h,l,c))
```

`@cached_fetch` expands to the full goal AST deterministically — it's a macro over goals, so nothing is lost to the verifier. ~60% fewer tokens for any goal that matches a known shape, and most do: fetch-cache, transform-validate, watch-react, batch-retry cover the bulk of real services.

### 5. Inference over declaration

Anything recoverable from context is omitted in the projection and reconstructed in the AST: types where inference is unambiguous, effect rows derived from callees (you only *write* effects at goal boundaries, where they're a budget), and contract fragments implied by types (`[T]` output from `[T]` input implies no invention of elements unless stated). The rule: **the projection carries only information the reader couldn't derive.** Everything derivable is the toolchain's job.

### Stacked effect, measured on the v1 examples

| Representation | Tokens (≈) |
|---|---|
| Equivalent Python + docstring + tests | 410 |
| Sigil v1 full projection | 180 |
| v2 first mention (template + dictionary) | 70 |
| v2 subsequent mentions (digest line) | 14 |
| v2 modification (patch) | ~size of change |

Honest caveat on the numbers: first-contact cost doesn't drop much — the model still has to learn the dictionary and templates once per project. The wins compound on *iteration*, which is fine, because iteration is 95% of an AI coding session. The other real cost is tooling: tiers 1–3 require the digest/expand/patch loop to exist in the harness, so the language is only as efficient as its MCP server. That makes the harness — not the grammar — the actual product.

## v2.1 addendum — cache and energy discipline

Token count is not the cost function. The actual per-turn cost (in compute, money, and energy) is closer to:

```
cost ≈ fresh_input_tokens·c_in + cached_input_tokens·c_cache + output_tokens·c_out + retries·everything
```

with `c_cache ≪ c_in < c_out`, and the `retries` term dominating badly-specified sessions. Three rules follow, and they constrain how v2's mechanisms may be used:

**R1 — The digest sheet is append-only within a session.** Cached prefix tokens cost a small fraction of fresh ones, so a byte-stable longer prefix beats an aggressively rewritten shorter one that invalidates the cache every turn. Therefore: never reorder digest lines, never re-intern the dictionary mid-session, never garbage-collect dead entries until a session boundary. A superseded definition gets a new digest line appended (`#a3f9 → #b1c2`); the old line stays. Naive minimization that rewrites the context each turn can cost *more* than v1.

**R2 — Spend output tokens last.** Output is generated one forward pass per token; input prefill is parallel and cache-eligible. This is why patches (mechanism 2) matter beyond their token count: they shrink the expensive side of the ledger. The harness should likewise prefer "expand `#hash` into input" over "regenerate from memory into output" whenever the model needs to see code again.

**R3 — Verification is the energy mechanism, not just the correctness mechanism.** A discarded generation is 100% waste. Running `verify` clauses costs effectively nothing next to a regeneration, so the harness runs contracts *before* showing output to a human and feeds failures back as patches against the failing subtree — never as "try again from scratch." Cutting the retry term is worth more than every projection trick combined.

Honest caveat: cache pricing and behavior are provider-specific and shift over time; R1 optimizes for the prevailing prefix-caching model and should be revisited if that changes. The energy framing inherits the same uncertainty as all per-query estimates — the *ratios* (cached ≪ fresh < output ≪ retry) are robust, the absolute numbers are not.

## Minimal bootstrap path

1. Define the AST schema (CBOR) + canonical hashing. ~1 week.
2. Text projection: parser + pretty-printer that round-trip losslessly. 
3. Interpreter for the pure fragment + contract runner.
4. Effect checker (it's just a row union with a budget comparison).
5. `goal` runner: LLM generates body → contracts + verify run → bind hash on pass.
6. Digest/expand/patch harness as an MCP server — this is what makes tiers 1–3 usable from a model. The harness owns R1–R3: append-only context assembly, expand-over-regenerate, and verify-before-display.
7. Project dictionary builder (frequency pass over the AST corpus) + a starter set of ~10 goal templates.

Steps 1–2 are very close to what an AST-compression layer already needs — the projection/canonical-form machinery is shared infrastructure.
