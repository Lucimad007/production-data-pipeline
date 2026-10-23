"""MCP server exposing the governed Breakout metric registry."""

from __future__ import annotations

import json
from typing import Any, cast

import pandas as pd
from mcp.server.mcpserver import MCPServer

from breakout.metrics import describe_metric as registry_describe
from breakout.metrics import list_metrics as registry_list
from breakout.metrics import query_metric as registry_query

mcp = MCPServer(
    name="breakout",
    title="Breakout creator intelligence",
    description="Governed metrics over a public YouTube creator lakehouse.",
    instructions=(
        "Start with list_metrics. Only query metrics that are registered. "
        "Report the metric name, grain, and the latest snapshot time with every answer. "
        "If a metric is not registered, say so instead of inventing a definition."
    ),
)


def _records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    payload = json.loads(frame.to_json(orient="records", date_format="iso"))
    return cast(list[dict[str, Any]], payload)


@mcp.tool()
def list_metrics() -> list[dict[str, Any]]:
    """List the governed metrics available in this data product."""
    return registry_list()


@mcp.tool()
def describe_metric(name: str) -> dict[str, Any]:
    """Return the definition, grain, owner, dimensions, SQL, and examples for a metric."""
    return registry_describe(name)


@mcp.tool()
def query_metric(name: str, limit: int = 100) -> list[dict[str, Any]]:
    """Run a registered metric. The row limit is clamped to 1,000."""
    return _records(registry_query(name, limit=limit))


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
