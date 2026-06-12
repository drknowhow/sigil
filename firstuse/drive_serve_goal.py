#!/usr/bin/env python3
"""Scenario B: does the goal -> verify -> bind loop (Sigil's headline) work
through the `sigil serve` MCP surface?

We build a .sg module (goal + buggy impl) into a fresh store via the CLI, then
serve that store and try to drive verify purely as an MCP client would.
"""
import asyncio
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
SG = HERE / "sample" / "pricing.sg"


def show(t, o):
    print(f"\n===== {t} =====")
    print(o if isinstance(o, str) else json.dumps(o, indent=2, default=str))


def _text(r):
    return "\n".join(getattr(c, "text", str(c)) for c in (getattr(r, "content", []) or []))


async def main():
    store = tempfile.mkdtemp(prefix="sigil_scenarioB_")
    build = subprocess.run(
        ["sigil", "build", str(SG), "--store", store, "--json"],
        capture_output=True, text=True,
    )
    info = json.loads(build.stdout)
    goal_hash = info["goals"]["triple"]
    show("CLI build registered goal (out-of-band, NOT an MCP tool)",
         {"goal_hash": goal_hash, "store": store})

    params = StdioServerParameters(command="sigil", args=["serve", "--root", store])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Does a freshly served store surface its pre-built goals?
            show("sheet() on fresh serve of a store that already has a goal",
                 repr(_text(await session.call_tool("sheet", {}))))

            # Verify the goal by the hash we learned from the build output.
            show("verify(goal_hash, inputs={n:4})  [impl is buggy: n*2]",
                 _text(await session.call_tool(
                     "verify", {"goal": goal_hash, "inputs": {"n": 4}})))

            # Can we even discover the impl fn hash to patch it? Only by lifting
            # the generated .py the build wrote. Try lifting it in.
            gen_py = SG.with_name("pricing.py")
            if gen_py.exists():
                show("lift(generated pricing.py) to get the impl onto the sheet",
                     _text(await session.call_tool("lift", {"path": str(gen_py)})))
                show("sheet() after lifting the impl",
                     _text(await session.call_tool("sheet", {})))

    print(f"\n[store was: {store}]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
