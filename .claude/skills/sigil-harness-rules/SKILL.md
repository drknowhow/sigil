---
name: sigil-harness-rules
description: MCP harness implementation rules for Sigil (digest/expand/patch/verify/lift tools and the R1-R3 cost discipline). ALWAYS consult before writing or modifying anything in src/sigil/harness/ (server.py, context.py), the MCP tool contract, session context assembly, or the patch-repair loop. Use together with the mcp-builder skill, which covers generic MCP server mechanics; this skill covers what makes the Sigil harness correct.
---

# Sigil Harness Rules

The harness is the product. The grammar without this server saves roughly nothing.
Read the mcp-builder skill for FastMCP mechanics; this skill defines Sigil-specific behavior.

## Tool contract (frozen — changing it requires a docs/decisions.md entry)
| tool | in | out | invariants |
|---|---|---|---|
| lift | path | sheet + stats | idempotent; re-lift reports changed hashes as `old -> new` |
| sheet | — | digest lines | append-only per session (R1) |
| expand | hash | full projection | logs expansion (feeds cost stats) |
| patch | hash, ops | new hash + verify result | auto-verify (R3); malformed-op error includes op index + location |
| verify | goal hash | pass/fail + clause detail | cached by (goal,impl); subprocess + timeout |

## R1 — append-only context (implement in harness/context.py, not in server handlers)
- The session sheet is an ordered log. Permitted op: append. Forbidden: reorder, rewrite, delete, re-intern dictionary entries mid-session.
- Superseding a definition appends `#old -> #new <sig>`; the old line stays.
- GC happens only at session boundaries. A session_close summary may emit a compacted sheet for the *next* session.
- Test: for any sequence of harness ops, sheet history is prefix-stable (every earlier sheet is a byte prefix of every later one).

## R2 — expand over regenerate
- Tool descriptions must instruct the model: to see code again, call expand; never reconstruct code from memory into output.
- expand responses are cache-friendly: byte-identical for identical hashes, forever.

## R3 — verify before display
- patch never returns success without a verify result attached (or an explicit `unverified: no goal bound`).
- On verify failure, return structured feedback: failing clause, observed values, and the subtree hash to target — phrased for a *patch against that subtree*, never "regenerate the function".
- Failure responses must be small (<300 tokens) — they are themselves part of the cost model.

## Error & safety conventions
- All tool errors: cause + remedy + machine-parseable `code` field.
- lift executes user code? NO — parse only. verify? YES — subprocess, timeout (default 10s), env stripped; network blocking is best-effort in v1.0 and the gap is documented honestly in limitations.md.
