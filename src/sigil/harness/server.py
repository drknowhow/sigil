"""FastMCP wiring for the Sigil harness (use with: sigil serve).

Tool descriptions deliberately encode R2/R3 instructions for the model
(sigil-harness-rules skill): expand over regenerate; patch failing subtrees,
never regenerate functions. Errors return cause + remedy + machine code.
"""

from __future__ import annotations

from pathlib import Path

from sigil.core.patch import PatchError
from sigil.harness.core import Harness

INSTRUCTIONS = """Sigil harness. Work through digests, not files:
1) lift(path) or the preloaded sheet gives one line per definition.
2) Read the sheet(); expand(hash) ONLY what you must read or modify (R2 —
   never reconstruct code from memory into your output).
3) Edit via patch(hash, ops) — ops address the canonical form; output scales
   with the change, not the file. Patches auto-verify (R3).
4) On verify failure, patch the reported subtree; never regenerate functions.
The sheet is append-only within a session (R1): superseded entries append
'#old -> #new'; earlier lines never move."""


def create_server(root: str = "."):
    from mcp.server.fastmcp import FastMCP

    h = Harness(Path(root))
    mcp = FastMCP("sigil", instructions=INSTRUCTIONS)

    def _err(exc: Exception) -> dict:
        return {"error": {"code": getattr(exc, "code", "invalid"), "message": str(exc)}}

    @mcp.tool()
    def lift(path: str) -> str:
        """Lift Python source at `path` into the digest sheet (one line per
        definition: #hash name(sig) effects). Idempotent: re-lifting unchanged
        code appends nothing; changed definitions append '#old -> #new'.
        Parse-only — never executes the lifted code."""
        try:
            return h.lift(path)
        except ValueError as exc:
            return str(_err(exc))

    @mcp.tool()
    def sheet() -> str:
        """The session digest sheet (append-only; R1). Read this instead of
        files. '?' marks static guesses; 'provisional' marks unverified goals."""
        return h.sheet()

    @mcp.tool()
    def expand(hash: str, form: str = "source") -> str:
        """Full projection of one definition by #hash. Byte-identical for the
        same hash, forever — call this whenever you need to see code again
        instead of reconstructing it from memory (R2). form='canonical'
        returns the patchable data form — derive patch op paths from it
        instead of guessing."""
        try:
            return h.expand(hash, form=form)
        except ValueError as exc:
            return str(_err(exc))

    @mcp.tool()
    def load_module(source: str, name: str = "<mcp>") -> dict:
        """Load a Sigil module (goals + fns) from source text: registers
        goals in the store, puts definitions, appends sheet lines. This is the
        MCP path for creating goals — no CLI round-trip needed. Returns
        {module, goals: {name: hash}, fns: {name: hash}}."""
        try:
            return h.load_sigil_source(source, name=name)
        except ValueError as exc:
            return _err(exc)

    @mcp.tool()
    def patch(hash: str, ops: list[dict], inputs: dict | None = None) -> dict:
        """Apply AST patch ops to #hash; returns the new hash plus a verify
        result (R3 — never edit-without-verify). Each op: {"path": dotted path
        into the canonical form (see expand), "op": replace|insert|delete,
        "value": ...}. On verify failure you get the failing clause, observed
        values, and the subtree hash to target — patch that subtree; do NOT
        regenerate the function."""
        try:
            return h.patch(hash, ops, inputs=inputs)
        except (PatchError, ValueError) as exc:
            return _err(exc)

    @mcp.tool()
    def verify(goal: str, inputs: dict | None = None, timeout: float = 10.0) -> dict:
        """Run a goal's verify clauses (subprocess-isolated, cached by
        (goal,impl) hash — unchanged code is a cache hit). Passing binds
        goal<->impl; anything else stays 'provisional'."""
        try:
            return h.verify(goal, inputs=inputs, timeout=timeout)
        except ValueError as exc:
            return _err(exc)

    @mcp.tool()
    def session_close() -> dict:
        """End-of-session stats plus a compacted sheet for the NEXT session
        (compaction never happens mid-session — R1)."""
        return h.session_close()

    return mcp
