#!/usr/bin/env python3
"""Demo: the AI PROPOSES the checklist (Tier-3) — and can't fake it.

The AI is handed an undocumented function `clamp(x, lo, hi)` (keep a number
within a low/high range). It proposes rules it thinks should hold. Each
proposal is validated against the REAL code; it only 'binds' (counts as an
accepted spec) if it actually passes. A plausible-but-wrong proposal is
rejected, not trusted.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = Path(__file__).parent
MATHLIB = HERE.parent / "sample" / "mathlib.py"


def _text(r):
    return "\n".join(getattr(c, "text", str(c)) for c in (getattr(r, "content", []) or []))


def _json(r):
    import json
    sc = getattr(r, "structuredContent", None)
    if sc:
        return sc
    try:
        return json.loads(_text(r))
    except Exception:
        return _text(r)


def verdict(res):
    v = res.get("verify")
    if isinstance(v, dict):
        st = v.get("status")
        bad = [c for c in v.get("clauses", []) if not c[1]]
        return st, (bad[0] if bad else None)
    return v, None


async def main():
    store = tempfile.mkdtemp(prefix="sigil_propose_")
    params = StdioServerParameters(command="sigil", args=["serve", "--root", store])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            await session.call_tool("lift", {"path": str(MATHLIB)})
            sheet = _text(await session.call_tool("sheet", {}))
            clamp = None
            for line in sheet.splitlines():
                t = line.strip().split()
                if len(t) >= 2 and t[0].startswith("#") and t[1].startswith("clamp"):
                    clamp = t[0]
            print("The AI is handed an undocumented function (no checklist exists):")
            print(f"    clamp(x, lo, hi)        [seen on the sheet as {clamp}]")
            sample = {"x": 50, "lo": 0, "hi": 10}
            print(f"    (validated against the real code with {sample})\n")

            print("1) AI PROPOSES the right rule: 'the result stays within [lo, hi]'")
            print("     checks: out >= lo , out <= hi")
            r = _json(await session.call_tool("propose_contract", {
                "fn_hash": clamp, "clauses": ["out >= lo", "out <= hi"], "inputs": sample}))
            st, bad = verdict(r)
            print(f"     -> {st.upper()}: " + (
                "both checks held; the proposal is now BOUND to the code (accepted)."
                if st == "pass" else f"failed at {bad}"))

            print("\n2) AI PROPOSES a plausible-but-WRONG rule: 'it never changes its input'")
            print("     check: out == x")
            r = _json(await session.call_tool("propose_contract", {
                "fn_hash": clamp, "clauses": ["out == x"], "inputs": sample}))
            st, bad = verdict(r)
            if st == "fail" and bad:
                print(f"     -> REJECTED (stays provisional): {bad[0]} gave {bad[2]}")
                print("        the AI could NOT launder a guess into a spec.")
            else:
                print(f"     -> {st}")

    print(f"\n[store: {store}]")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(main())
