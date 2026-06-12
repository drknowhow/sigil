"""Regression tests driving `sigil serve` through a REAL stdio MCP client —
not the in-process Harness shortcut (firstuse report, 2026-06-12).

The verify deadlock: the verify subprocess inherited the server's stdin,
which under stdio transport IS the JSON-RPC pipe (also a security hole:
untrusted code could read client traffic). Fix: stdin=DEVNULL in the runner.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("mcp")

ROOT = Path(__file__).parent.parent.parent

SG = """module mathx

goal triple {
  intent: "triples"
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


def _text(result) -> str:
    return "\n".join(getattr(c, "text", "") for c in (result.content or []))


async def _drive(store_dir: str) -> dict:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "sigil.cli", "serve", "--root", store_dir],
        env={
            "PYTHONPATH": str(ROOT / "src"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        out: dict = {}
        r = await session.call_tool("load_module", {"source": SG})
        out["load"] = json.loads(_text(r))
        r = await session.call_tool("sheet", {})
        out["sheet"] = _text(r)
        goal_hash = out["load"]["goals"]["triple"]
        t0 = time.perf_counter()
        r = await session.call_tool(
            "verify", {"goal": goal_hash, "inputs": {"n": 4}, "timeout": 8.0}
        )
        out["verify_secs"] = time.perf_counter() - t0
        out["verify"] = json.loads(_text(r))
        return out


def test_verify_over_real_stdio_does_not_deadlock(tmp_path) -> None:
    out = asyncio.new_event_loop().run_until_complete(_drive(str(tmp_path)))
    v = out["verify"]
    assert v["status"] == "fail", v  # buggy impl: a real verdict, NOT a timeout
    assert out["verify_secs"] < 6, f"served verify took {out['verify_secs']:.1f}s (deadlock?)"
    failing = [c for c in v["clauses"] if not c[1]]
    assert failing and failing[0][0] == "out == n * 3"


def test_goal_loop_reachable_from_mcp_alone(tmp_path) -> None:
    # N1: load_module registers goals through the MCP surface (no CLI needed)
    out = asyncio.new_event_loop().run_until_complete(_drive(str(tmp_path)))
    assert "triple" in out["load"]["goals"]
    assert "goal triple" in out["sheet"] and "provisional" in out["sheet"]
