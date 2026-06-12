"""FastMCP wiring smoke test: the frozen tool contract is fully registered."""

import asyncio

import pytest

mcp_mod = pytest.importorskip("mcp")


def test_all_contract_tools_registered(tmp_path) -> None:
    from sigil.harness.server import create_server

    server = create_server(str(tmp_path))
    tools = asyncio.new_event_loop().run_until_complete(server.list_tools())
    names = {t.name for t in tools}
    assert {"lift", "sheet", "expand", "patch", "verify", "session_close"} <= names
    # R2/R3 instructions live in the descriptions (sigil-harness-rules skill)
    by_name = {t.name: t.description or "" for t in tools}
    assert "regenerate" in by_name["patch"]  # "do NOT regenerate the function"
    assert "reconstruct" in by_name["expand"] or "memory" in by_name["expand"]
