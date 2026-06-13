# Quickstart — install → lift → first patch in 5 minutes

```bash
pip install -e ".[dev,harness]"     # from the repo root (Python 3.11+)
```

**1. Lift existing Python (30s).** Point Sigil at any code:

```bash
sigil lift examples/lift-legacy/webapp.py
```

You get a digest sheet — one line per definition: `#hash name(sig) effects`.
`#d4b8 fetch_user(user_id) -> ? !clock !fs !net` means: content-addressed
identity `#d4b8`, and the function touches the clock, filesystem, and network.
`?` marks static guesses (`pure?`, `!unsafe?`) — never silenced.

**2. Write a goal + implementation in Sigil (2 min).** See
`examples/new-module/prices.sg`. Build it:

```bash
sigil build examples/new-module/prices.sg --store .
```

Contracts become dev-mode assertions (stripped under `SIGIL_RELEASE=1`); the
effect budget is checked statically — try `over_budget.sg` to see a rejection
that names the violating call chain.

**3. Verify and bind (1 min).**

```bash
echo '{"tickers": ["AAPL"], "start": "a", "end": "b"}' > inputs.json
sigil verify '#<goal-hash-from-build-output>' --store . --inputs inputs.json
```

Verify runs subprocess-isolated with a timeout; a pass binds goal↔impl; a
re-run on unchanged code is a <50ms cache hit.

**4. First patch (1 min).** Start the harness — `sigil serve --root .` — and
connect it to Claude Code/Cowork as an MCP server (see harness-guide.md).
A session over an existing store starts with its goals already on the sheet;
`load_module` creates new goals over pure MCP. Edits happen as AST patches
against hashes (derive paths from `expand(hash, form="canonical")`),
auto-verified before you see success. The scripted version of this loop:
`python3 examples/agent-session/run_session.py`.

## v2 at a glance

Past the basics, v2 adds: write plain Python with `@sigil.bind(verify=[...], fx="pure")`
instead of `.sg`; declare read/write modes and module budgets (`!fs.read`, a module-level
`fx:` line); assert properties across functions with `invariant { over: a, b verify: ... }`;
lift and reproducibility-check R (`sigil lift x.R`, `sigil check-r`); and gate CI with
`sigil check --against origin/main` or stay live with `sigil watch .`. Full reference:
`docs/language-guide.md`, `docs/harness-guide.md`, and the project hero page's Changelog tab.
