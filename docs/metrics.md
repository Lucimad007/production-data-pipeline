# Governed metrics and the MCP server

Breakout exposes a small, owned metric registry instead of raw text-to-SQL. The registry is the contract between the marts, the dashboard, and any agent.

## Why a registry

An agent asked "which topics broke out?" can invent a join, pick the wrong grain, or treat a hidden count as zero. A registry removes that failure surface:

- The SQL is authored and reviewed by a human.
- Every metric has a name, grain, owner, dimensions, and examples.
- The caller can choose a metric and a row limit, not a table or a query.
- The same definition is used by the CLI, the MCP server, and (later) the dashboard.

## Metrics

| Metric | Grain | Question |
|---|---|---|
| `channel_overview` | channel | What does the channel scorecard look like? |
| `breakout_rate` | channel | What share of videos broke out? |
| `top_breakouts` | video | Which videos performed best? |
| `topic_performance` | topic | Which topics work? |
| `publish_timing` | day + hour | When should the creator publish? |
| `engagement_summary` | channel | What is the engagement baseline? |
| `data_freshness` | snapshot | How fresh is the data? |
| `quarantine_summary` | quarantine | Are there malformed records? |

Definitions live in `metrics/video_performance.yml`.

## CLI

```powershell
uv run breakout metrics
uv run breakout metric breakout_rate
uv run breakout metric top_breakouts --limit 5
```

The CLI prints a DataFrame. Unknown metrics fail with a list of valid choices.

## MCP server

The server uses the MCP 2.x `MCPServer` API and exposes three tools:

- `list_metrics`
- `describe_metric`
- `query_metric`

Start it over stdio:

```powershell
uv run breakout-mcp
```

Claude Desktop or Cursor configuration:

```json
{
  "mcpServers": {
    "breakout": {
      "command": "uv",
      "args": [
        "run",
        "--directory",
        "C:/Users/EXO/Desktop/repos/production-data-pipeline",
        "python",
        "-m",
        "breakout.mcp_server"
      ]
    }
  }
}
```

Use an absolute path. On macOS/Linux, replace the directory with your clone path.

## Example agent flow

1. `list_metrics` -> see the eight governed metrics.
2. `describe_metric("breakout_rate")` -> grain, owner, SQL, examples.
3. `query_metric("breakout_rate")` -> one row: 13.4% across 507 videos.
4. `query_metric("data_freshness")` -> latest snapshot and count.

The agent should include the metric name, grain, and freshness in the answer. If a question cannot be answered by a registered metric, it should say so.

## Guardrails

- **Registry-only execution.** The caller cannot pass SQL, table names, or column names.
- **Bounded rows.** `limit` is clamped to 1,000.
- **Author-controlled SQL.** Definitions are reviewed like code.
- **Read-only role recommended.** The local demo uses a read-only workflow; a production deployment should use a database role with `SELECT` only.
- **No PII.** Comment authors are hashed; the registry does not expose comment text.
- **Audit.** The CLI and MCP calls are easy to log; the next step is structured trace storage.

## What is not built

- RAG over comments and transcripts.
- An LLM client that chooses tools and writes answers.
- An eval harness with SQL correctness, faithfulness, relevance, and refusal metrics.
- Cube or the dbt Semantic Layer. The registry is deliberately smaller; see [ADR 0005](adr/0005-metric-registry-vs-semantic-layer.md).

Those are the remaining pieces of the AI workstream, not hidden claims.
