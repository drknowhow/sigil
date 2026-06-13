# Harness guide — connecting Claude Code / Cowork, and R1–R3 operationally

Start: `sigil serve --root <dir>` (stdio MCP server; needs `pip install "sigil[harness]"`).

Claude Code: `claude mcp add sigil -- sigil serve --root /path/to/repo`.
Cowork/Claude Desktop: add a custom MCP server with command `sigil`, args
`serve --root /path/to/repo`.

Tools: `lift(path)` (.py and .R), `sheet()`, `expand(hash, form?)`,
`patch(hash, ops, inputs?)`, `patch_snippet(hash, snippet, inputs?)`,
`verify(goal, inputs?)`, `verify_invariant(hash, inputs?)`,
`load_module(source)`, `propose_contract(fn_hash, clauses, inputs?)` (Tier 3),
`session_close()`. A session over an existing store starts with its registered
goals already on the sheet; `load_module` creates goals over pure MCP
(D-030). `expand(hash, form="canonical")` returns the patchable data form —
derive patch paths from it.

## The three rules, operationally

**R1 — the sheet only grows.** Within a session the digest sheet is an
append-only log: superseded definitions append `#old -> #new`; earlier lines
never move. This keeps your cached prompt prefix byte-stable — rewriting
context every turn can cost more than not using Sigil at all. Compaction
happens only in `session_close`, for the *next* session.

**R2 — expand, don't regenerate.** Need to see code again? `expand(#hash)` —
byte-identical forever, cache-friendly, and cheaper than the model re-emitting
code from memory into output tokens (the expensive side of the ledger).

**R3 — verify before display.** Every `patch` returns with a verify result
attached (or an explicit `unverified: ...` reason). Failures come back small
and structured — failing clause, observed values, the subtree hash to target —
phrased for a follow-up *patch*, never "try again from scratch". Cutting the
retry term is worth more than every projection trick combined.

## Teaching the agent the workflow

The repo ships `.claude/skills/sigil-agent-workflow` — Claude Code loads it
automatically when working in a repo containing it; it encodes the
sheet→expand→patch→verify discipline, the patch-op cheat-sheet, and the
failure playbook so the model doesn't have to rediscover R1–R3 each session.
Copy the skill directory into any repo you serve with `sigil serve`.

## Patch ops

`{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}` —
paths are dotted addresses into the canonical form shown by
`expand(hash, form="canonical")` (lifted Python sits under `body.data.…`);
ops are `replace` / `insert` / `delete`. Malformed ops fail with the op index,
the failing path token, and a machine-readable `code`.

## Safety

`lift` parses, never executes. `verify` executes — subprocess-isolated with a
timeout. Network blocking during verify is best-effort in v1.0 (limitations.md #8).
