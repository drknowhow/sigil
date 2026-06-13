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

## Re-measuring on your own repo

```bash
sigil lift path/to/repo --json > sheet.json   # hashes + sheet
python3 scripts/measure_costs.py              # this repo's artifacts
```

Caveats: cache pricing is provider-specific and shifts; the *ratios*
(cached ≪ fresh < output ≪ retry) are robust, absolute numbers are not.
