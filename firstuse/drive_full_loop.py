#!/usr/bin/env python3
"""1.0.1 re-test: the FULL headline loop entirely over pure MCP (no CLI
round-trip), using the new load_module + canonical-expand tools.

load_module(buggy) -> sheet -> verify(FAIL) -> expand(canonical) -> patch(fix)
-> auto-verify(PASS) binds goal<->impl. This was unreachable in the first-use
report (no MCP tool created goals).
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

BUGGY = """module pricing

goal triple {
  intent: "triple the input"
  in: n Int
  out: Int
  fx: pure
  verify:
    out == n * 3
}

fn triple(n Int) -> Int
  pure
{
  ret n * 2
}
"""


def show(t, o):
    print(f"\n===== {t} =====")
    print(o if isinstance(o, str) else json.dumps(o, indent=2, default=str))


def _text(r):
    return "\n".join(getattr(c, "text", str(c)) for c in (getattr(r, "content", []) or []))


def _json(r):
    sc = getattr(r, "structuredContent", None)
    if sc:
        return sc
    try:
        return json.loads(_text(r))
    except Exception:
        return _text(r)


async def main():
    store = tempfile.mkdtemp(prefix="sigil_fullloop_")
    params = StdioServerParameters(command="sigil", args=["serve", "--root", store])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = [t.name for t in (await session.list_tools()).tools]
            show("tool surface (1.0.1)", tools)

            info = _json(await session.call_tool("load_module", {"source": BUGGY}))
            show("load_module(buggy pricing)  [NEW in 1.0.1]", info)
            goal_h = info["goals"]["triple"]
            fn_h = info["fns"]["triple"]

            show("sheet()", _text(await session.call_tool("sheet", {})))

            show("verify(goal, n=4)  expect FAIL (impl is n*2)",
                 _json(await session.call_tool(
                     "verify", {"goal": goal_h, "inputs": {"n": 4}})))

            show("expand(fn, form=canonical)  [NEW: derive patch path, don't guess]",
                 _text(await session.call_tool(
                     "expand", {"hash": fn_h, "form": "canonical"})))

            # fix ret n*2 -> n*3 by patching the literal; auto-verify (R3)
            ops = [{"path": "body.stmts.0.value.right.val", "op": "replace", "value": "3"}]
            patched = _json(await session.call_tool(
                "patch", {"hash": fn_h, "ops": ops, "inputs": {"n": 4}}))
            show("patch(fix) -> auto-verify (R3) expect PASS + bind", patched)

            show("verify(goal, n=4) again  expect cached PASS + goal verified",
                 _json(await session.call_tool(
                     "verify", {"goal": goal_h, "inputs": {"n": 4}})))

            show("sheet() final (binding line appended)",
                 _text(await session.call_tool("sheet", {})))

    print(f"\n[store was: {store}]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
