#!/usr/bin/env python3
"""First-use driver: talk to a live `sigil serve` MCP server over stdio,
exactly as an MCP client (Claude Code/Desktop) would. Logs every tool call
and result so a human can audit the real harness surface (not the in-process
Harness shortcut used by examples/agent-session/run_session.py).

Scenario A here: lift a fresh buggy Python file, read the sheet, expand the
buggy fn, fix it via a patch (first with the skill-documented path shape to
see the error UX, then with the real canonical path), and probe what the
verify surface does when no goal is bound.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
SAMPLE = HERE / "sample" / "discount.py"


def show(title, obj):
    print(f"\n===== {title} =====")
    print(obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str))


def _text(result):
    parts = [getattr(c, "text", str(c)) for c in (getattr(result, "content", []) or [])]
    out = "\n".join(parts)
    # tool results that are dicts come back as a JSON/py-repr string; pass through
    return out


# canonical BinOp for `pct / 100`, hand-built in the Python-AST tuple encoding
PCT_OVER_100 = [
    "BinOp",
    [
        ["left", ["Name", [["id", "pct"], ["ctx", ["Load", []]]]]],
        ["op", ["Div", []]],
        ["right", ["Constant", "int", "100"]],
    ],
]


async def main():
    store = tempfile.mkdtemp(prefix="sigil_firstuse_store_")
    params = StdioServerParameters(command="sigil", args=["serve", "--root", store])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            r = await session.call_tool("lift", {"path": str(SAMPLE)})
            show("lift(discount.py)", _text(r))

            sheet = _text(await session.call_tool("sheet", {}))
            show("sheet()", sheet)

            # definition lines: '#hash name(...) ...'; supersession lines: '#a -> #b'
            hashes = {}
            for line in sheet.splitlines():
                t = line.strip().split()
                if len(t) >= 2 and t[0].startswith("#") and t[1] != "->":
                    hashes[t[1].split("(")[0]] = t[0]
            show("parsed name->hash", hashes)
            target = hashes["apply_discount"]

            show(f"expand({target})  [apply_discount source only]",
                 _text(await session.call_tool("expand", {"hash": target})))

            # (a) patch with the path shape the skill's cheat-sheet implies for
            #     lifted Python ('body.0.value...') — expected to error.
            bad = [{"path": "body.0.value.right.right", "op": "replace", "value": PCT_OVER_100}]
            show("patch attempt #1 (skill-doc-style path) -> error UX",
                 _text(await session.call_tool("patch", {"hash": target, "ops": bad})))

            # (b) patch with the REAL canonical path (derived by dumping to_data).
            good = [{"path": "body.data.body.0.value.right.right",
                     "op": "replace", "value": PCT_OVER_100}]
            show("patch attempt #2 (real canonical path)",
                 _text(await session.call_tool("patch", {"hash": target, "ops": good})))

            show("sheet() after patch (R1 append-only)",
                 _text(await session.call_tool("sheet", {})))

            # verify against a fn hash (there is no goal) — what comes back?
            show("verify(apply_discount-hash)  [no goal exists]",
                 _text(await session.call_tool("verify", {"goal": target})))

            show("session_close()", _text(await session.call_tool("session_close", {})))

    print(f"\n[store was: {store}]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
