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
