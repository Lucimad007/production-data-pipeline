from __future__ import annotations

import asyncio

from breakout.mcp_server import mcp


def test_mcp_server_is_configured() -> None:
    assert mcp.name == "breakout"
    assert "governed" in (mcp.description or "").lower()


def test_mcp_server_exposes_only_governed_tools() -> None:
    tools = asyncio.run(mcp.list_tools())
    assert {tool.name for tool in tools} == {
        "list_metrics",
        "describe_metric",
        "query_metric",
    }
