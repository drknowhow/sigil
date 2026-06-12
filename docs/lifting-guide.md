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
