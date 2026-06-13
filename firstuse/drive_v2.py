#!/usr/bin/env python3
"""v2 first-use: drive the new v2 MCP surface over a live `sigil serve` stdio
session — multi-fn invariants, Tier-3 propose_contract (the agent is the
proposer), neutral-IR canonical expand, and patch-by-snippet.
"""
import asyncio
import json
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
MATHLIB = HERE / "sample" / "mathlib.py"

CODEC = """module codec

fn enc(x Int) -> Int
  pure
{
  ret x + 1
}

fn dec(y Int) -> Int
  pure
{
  ret y - 2
}

invariant round_trip {
  in: x Int
  over: enc, dec
  verify:
    dec(enc(x)) == x
}
"""

DEC_FIXED = """fn dec(y Int) -> Int
  pure
{
  ret y - 1
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
    store = tempfile.mkdtemp(prefix="sigil_v2_")
    params = StdioServerParameters(command="sigil", args=["serve", "--root", store])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            show("v2 tool surface", [t.name for t in (await session.list_tools()).tools])

            # ---- A. Multi-fn invariant (P3.9) ----
            info = _json(await session.call_tool("load_module", {"source": CODEC}))
            show("load_module(codec: enc=x+1, dec=y-2 BUG, invariant round_trip)", info)
            inv_h = info["invariants"]["round_trip"]
            dec_h = info["fns"]["dec"]

            show("sheet()", _text(await session.call_tool("sheet", {})))

            show("verify_invariant(round_trip, x=4)  expect FAIL (dec(enc(4))=3)",
                 _json(await session.call_tool(
                     "verify_invariant", {"invariant": inv_h, "inputs": {"x": 4}})))

            show("patch_snippet(dec -> y-1)  [v1.1: no path authoring] auto-reverify",
                 _json(await session.call_tool(
                     "patch_snippet", {"hash": dec_h, "snippet": DEC_FIXED, "inputs": {"x": 4}})))

            show("verify_invariant(round_trip, x=4) again  expect PASS + bind",
                 _json(await session.call_tool(
                     "verify_invariant", {"invariant": inv_h, "inputs": {"x": 4}})))

            # ---- B. Tier-3 propose_contract (I am the proposer) ----
            show("lift(mathlib.py)", _text(await session.call_tool(
                "lift", {"path": str(MATHLIB)})))
            sheet = _text(await session.call_tool("sheet", {}))
            hashes = {}
            for line in sheet.splitlines():
                tk = line.strip().split()
                if len(tk) >= 2 and tk[0].startswith("#") and tk[1] != "->":
                    hashes[tk[1].split("(")[0]] = tk[0]
            dbl = hashes["double"]

            show("expand(double, form=canonical)  [v2 neutral IR, NOT Python tuples]",
                 _text(await session.call_tool(
                     "expand", {"hash": dbl, "form": "canonical"})))

            show("propose_contract(double, ['out == n * 2'], n=5)  expect VALID -> bind",
                 _json(await session.call_tool(
                     "propose_contract",
                     {"fn_hash": dbl, "clauses": ["out == n * 2"], "inputs": {"n": 5}})))

            show("propose_contract(double, ['out == n * 3'], n=5)  expect provisional/FAIL",
                 _json(await session.call_tool(
                     "propose_contract",
                     {"fn_hash": dbl, "clauses": ["out == n * 3"], "inputs": {"n": 5}})))

            show("session_close()", _json(await session.call_tool("session_close", {})))

    print(f"\n[store was: {store}]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
