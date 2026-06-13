# Sigil

Contract-first, content-addressed language + toolchain for human–AI coding.
Status: v1.0 build in progress — see `docs/STATUS.md`. Spec and plan in `docs/plan/`.

## Quickstart (current state: Phases 0–1)

```bash
pip install -e ".[dev]"
pytest -q                          # full suite
sigil lift path/to/code            # Python -> digest sheet (Tier 1 structure + Tier 2 effects)
sigil lift path/to/code --json     # machine-readable
sigil build module.sg --store .    # Sigil -> Python; static effect check; register goals
sigil verify '#<goal>' --store . --inputs in.json   # subprocess-isolated, cached verify
sigil lift analysis.R              # v2: R frontend (Tier-1 hashing + token-rule effects)
sigil check --against origin/main  # v2: CI gate — fail on regressed/dropped contracts
sigil watch .                      # v2: re-verify on every save
python3 examples/new-module/run_demo.py   # end-to-end demo incl. the rejection
```

A digest sheet line:

```
#f22c fetch_prices(tickers, start, end) -> ? !fs !net
```

`#f22c` is a content address (sha256 over canonical CBOR of the AST — formatting,
comments and docstrings never change it). `!fs !net` is the inferred effect row;
`?` marks static guesses (`pure?`, `!unsafe?`) — Tier 2 over-approximates, never
silences uncertainty.

`sigil serve --root .` runs the MCP harness (stdio): tools `lift`, `sheet`,
`expand(hash, form?)`, `patch`, `verify`, `load_module`, `session_close` under
the R1–R3 cost rules — field-tested over live MCP (firstuse/, v1.0.1).
Note: the PyPI name "sigil" belongs to an unrelated project; this distribution
is `sigil-lang` (import and CLI remain `sigil`). See
`examples/agent-session/` for a scripted transcript, and
`.claude/skills/sigil-agent-workflow` for the drop-in agent skill that teaches
the workflow. Project hero page + quick guide: open `site/index.html`. Explainer video
(Remotion): `cd video && npm install && npm run studio` (or `npm run render`).

## What's new in v2.0

- **Language-neutral IR** — lifted code hashes to a neutral IR; `sigil migrate` bumps a
  v1 store's format while keeping old objects readable.
- **R frontend** — `sigil lift script.R` (tokenizer-canonical Tier-1 + token-rule effects);
  `sigil check-r --fn analyze --args "[42]" --expect '#hash'` for reproducibility contracts.
- **Effect modes & module budgets** — `!fs.read`/`!fs.write`, `!db`, and whole-module `fx:`
  budgets (`.sg` header or `__sigil_fx__` in Python).
- **`@sigil.bind`** — write plain Python; Sigil lifts on import and checks the budget statically.
- **Multi-fn invariants** — `invariant { over: enc, dec  verify: dec(enc(x)) == x }`; patching
  either fn re-verifies.
- **Tier-3 propose/validate** — `propose_contract` (provisional until verified) + the
  `sigil from-pytest` draft bridge.

Benchmarks (token reduction, verify-cache latency, effect accuracy, lift throughput): `docs/benchmarks.md`, reproducible via `python3 scripts/benchmark.py`.

See `CHANGELOG.md` for the full v1.0.0 → v2.0.0 history, or open `site/index.html` → Changelog.
