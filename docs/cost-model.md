# Cost model — measured, not estimated

> **v2.0.1 update:** the neutral-IR sheets re-measure at **6.0x** on requests
> 2.34.2 (was 5.9x in v1). The full multi-metric benchmark — verify-cache
> latency, effect under-report rate, lift throughput, iteration-turn token
> budget, IR round-trip stability — lives in `docs/benchmarks.md`, produced by
> `scripts/benchmark.py`.

## Methodology

Numbers below are produced by `scripts/measure_costs.py` against this repo's
actual artifacts, using a **real production BPE tokenizer** — the Claude BPE
bundled offline with `anthropic==0.3.x` (the script prefers `tiktoken
cl100k_base` when its vocabulary is available; both are within a few percent
on code). Re-run it yourself; the script refuses to fall back to estimates.
The `≈N tok` figures printed in sheet footers remain chars/4 *estimates* and
are labeled as such — only this document carries measured numbers.

## Measured: digest sheet vs full source (first contact)

Tokenizer: Claude BPE (anthropic 0.3.x bundled tokenizer.json)

| source | full source (tok) | digest sheet (tok) | reduction |
|---|---|---|---|
| demo_module.py (4 fns) | 319 | 133 | 2.4x |
| lift-legacy webapp.py (15 fns) | 767 | 307 | 2.5x |
| requests 2.34.2 (6,385 lines) | 52,464 | 8,907 | 5.9x |

**Honest correction to the spec.** The spec's eyeballed claims ("a 10k-line
project becomes a ~200-line digest sheet", "90%+ context reduction") do not
survive measurement at first contact: on a real repo the sheet is **5.9x**
smaller (83%), not 10x+. Two reasons: real signatures are long (typed
parameters dominate sheet lines) and hashes tokenize poorly (~4–6 tokens
each). The spec is marketing until measured; these are the numbers.

## Where the spec's claim does hold: iteration

First contact is paid once. The session economics (v2.1 cost function) are
dominated by *iteration*, where the measured artifacts are:

| context route (agent-session example) | measured tokens |
|---|---|
| full module re-read | 42 |
| digest sheet, cached prefix (R1) | 14 |
| expand one implementation (R2) | 11 |
| patch as output (R3) | 18 |

On iteration turns the model re-reads the *sheet* (cache-eligible under R1,
so billed at cached-input rates), expands only what it edits, and emits
patches instead of files. For the requests repo that is 8,907 cached tokens
+ per-edit expansions of ~30–150 tokens, versus re-reading 52,464 fresh
tokens — the >10x claim is real *per iteration turn*, not per first read.

`cost ≈ fresh_in·c_in + cached_in·c_cache + out·c_out + retries·everything`
with `c_cache ≪ c_in < c_out`. R1 maximizes the cached term, R2/R3 shrink the
output and retry terms — R3 (auto-verify, patch-the-subtree feedback) attacks
the retry term, which dominates badly-specified sessions.

## What the saving actually is — and isn't (Muninn Part 2)

Three separate claims hide inside "lossless token compression via a terser
language." Measured, the win comes from none of them — and naming the real
mechanism makes the pitch *more* defensible, not less.

**A terser language does not save tokens.** The one lever a glyph syntax offers
— the math operators `∧ ≤ ≠` — actually *costs* tokens: real BPE tokenizers
split a non-ASCII operator into two tokens where the ASCII spelling is one.

| written as | tokens | written as | tokens |
|---|---|---|---|
| `and` | 1 | `∧` | 2 |
| `<=`  | 1 | `≤` | 2 |
| `!=`  | 1 | `≠` | 2 |

(This is well-known BPE behavior; re-run `scripts/measure_costs.py` with the
bundled Claude BPE to pin the exact counts on your tokenizer.) The printer now
emits ASCII by default for exactly this reason (D-044); glyphs are opt-in. And a
`.sg` file is *longer* than the equivalent Python — it adds contracts and effect
rows. The language is not where tokens are saved.

**"Compression" is the wrong word.** A digest-sheet line —
`#9407 fetch_prices(tickers, start, end) -> ? !net?` — is not a squeezed-down
function you could rebuild the body from. It is an **index card**: name, args,
effects, fingerprint. The body is filed away and fetched (`expand`) only when
needed. The saving is "don't carry what you aren't using this turn" — real and
valuable, but a different thing from compression.

**The actual lever is content addressing + small deltas.** A function's
fingerprint moves only when its meaning changes, so the index sheet is
byte-for-byte identical turn after turn — exactly the precondition for a model's
**prompt cache** to bill it at cached rates (R1). Edits ship as small structured
patches, not whole-file rewrites (R2/R3). Stable cacheable index + tiny edits =
the compounding win measured above. The corollary, said plainly: the
**contracts and effects** — arguably the most valuable part of Sigil — *add*
information. The best part of the project compresses nothing, and that is fine.

**The experiment that would settle it.** Take one real agent coding task and run
it two ways — (a) Sigil's sheet + patch protocol, vs (b) plain Python kept in a
prompt cache + an ordinary patch tool — and compare the real token bill. If
Sigil wins, the win is most likely the contracts/effects catching bad edits
(fewer retries), not terseness or compression. `scripts/benchmark.py` is where
that A/B belongs.

## Re-measuring on your own repo

```bash
sigil lift path/to/repo --json > sheet.json   # hashes + sheet
python3 scripts/measure_costs.py              # this repo's artifacts
```

Caveats: cache pricing is provider-specific and shifts; the *ratios*
(cached ≪ fresh < output ≪ retry) are robust, absolute numbers are not.
