---
name: sigil-agent-workflow
description: How to work on a Sigil-enabled codebase through the sigil MCP harness (sheet/expand/patch/verify tools). ALWAYS consult when connected to a `sigil serve` MCP server, when asked to read or edit code in a repo that has a .sigil store, when a patch or verify tool call fails, or before reading any source file in such a repo — the sheet replaces file reads.
---

# Working through the Sigil harness

You are connected to a repo's `sigil serve` MCP server. Work through digests,
not files. The loop is: **sheet → expand → patch → (auto)verify**.

## The discipline (R1–R3 — these save your context budget)

1. **Read the `sheet()` first, never the files.** One line per definition:
   `#hash name(sig) effects`. `pure?`/`!unsafe?` markers are honest static
   guesses; `provisional` means a goal is not yet verified.
2. **`expand(#hash)` only what you must read or modify.** Responses are
   byte-identical forever. Never reconstruct code from memory into your
   output — that converts cheap cached input into expensive output tokens.
3. **Edit with `patch(hash, ops, inputs?)`, never by writing files.** Output
   should scale with the change, not the file.
4. **Trust the verify verdict, not your read of the code.** Patches
   auto-verify; on failure you get the failing clause, observed values, and
   the subtree hash to target. Patch that subtree. Do NOT regenerate the
   function from scratch.
5. The sheet only grows within a session (`#old -> #new` lines mark
   supersessions). Do not ask for it to be rewritten or reordered.

## Patch ops cheat-sheet

Ops address the canonical data form shown by `expand`:

```json
{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}
```

- Path tokens: dict keys (`body`, `name`), list indices (`0`), or canonical
  host-AST field names. `op` ∈ replace | insert | delete.
- **Derive paths from `expand(hash, form="canonical")`** — it returns the
  exact data structure ops address. Never guess paths from the source view.
- Sigil-written fns: `body.stmts.<i>...`; literals end in `.val`.
- Lifted fns wrap a neutral IR under `body.data` (v2.0): a def is
  `["def", name, args, [body], …]`, so paths are positional —
  `body.data.3.0.1.2` reaches the repr of a returned constant
  (`["const", type, repr]`). Always derive from `expand(hash,
  form="canonical")`; prefer `patch_snippet` and let Sigil compute paths.
- Malformed ops fail with the op index + failing token (`code: bad_path`).
  Remedy: `expand` the hash and re-derive the path; don't guess twice.

## Verify and inputs

- Goals with declared `in:` parameters need `inputs` (a JSON object keyed by
  parameter names) — patch returns `unverified: inputs required` otherwise.
  Ask the user for representative inputs; never invent domain values silently.
- Verdicts: pass | fail | timeout | error. Only pass binds goal↔impl. A
  cached verdict (`cached: true`) is authoritative — hashes are immutable.

## When things look wrong

- `unverified: no goal bound` — the fn has no same-name goal; suggest writing
  one (goal + verify clauses) rather than editing blind.
- `!unsafe?` on a row — the analyzer could not resolve dynamics; treat the
  function as effectful until proven otherwise.
- Need a definition that is not on the sheet? `lift(path)` it in; re-lifts of
  unchanged code are no-ops.
