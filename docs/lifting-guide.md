# Lifting guide — what the tiers mean, reading `?`, when to trust what

| Tier | What | Trust |
|---|---|---|
| 1 | structure: AST, signatures, digests | total — deterministic parsing + hashing |
| 2 | effects (`!net`, `!fs`, ...) | sound-ish: may over-report, must not under-report |
| 3 | contracts/intent (LLM-proposed) | **untrusted until verified** — not in v1.0 |

**Reading `?`.** `pure?` = statically inferred purity, not proven. `!unsafe?` =
the analyzer hit something it cannot resolve (dynamic dispatch, a function
passed as a value, an unknown/cross-module import) and refuses to guess.
`?` is never stripped by formatting code — under-reporting is a bug,
over-reporting is noise (the prime directive).

**What Tier 2 catches** (benchmark: 33 labeled fixtures, zero under-reports;
hand-labeled 30-function spot-check on requests 2.34.2: see
tests/fixtures/oss/spotcheck-2026-06-11.md): import-rooted effects, taint
through assignments (`p = CACHE / name; p.read_text()` → `!fs`), annotations,
`with` targets, call results, and — since D-025 — local helper *return values*.

**Known gaps** (limitations.md): method calls on values whose origin the
analyzer lost are silent; effectful `@property` access without a call is
invisible; cross-module calls within your own repo are honest `!unsafe?`
rather than resolved. The roadmap answer is dynamic tracing, not optimism.

**Idempotence.** Re-lifting unchanged code yields identical hashes; changed
definitions appear as `#old -> #new` lines. Lifting never executes your code.

## Lifting R (v2.0)

`sigil lift script.R` reads top-level `name <- function(...)` definitions. Tier 1 is
**token-canonical**, not AST-based: the source is normalized to a token sequence, so
comments and whitespace never move a hash, but a real R parser (with non-standard
evaluation, promises, lazy args) is explicitly out of scope for v2.0 — see decisions
D-037. Tier-2 effects are token-rule based and deliberately noisy: `library()`,
`source()`, `do.call()`, and `eval()` earn `!unsafe?`, while `read.csv`/`write.csv`/
`download.file`/`set.seed` map to `!fs.read`/`!fs.write`/`!net`/`!rand`.

The reproducibility wedge is `sigil check-r script.R --fn analyze --args "[42]" --expect
'#hash'`: it runs the function through Rscript with a deparse-stable result hash, so
`analyze(seed=42) ≡ #abcd1234` becomes a checkable contract. Lifting needs no R runtime;
`check-r` needs `Rscript` on PATH.
