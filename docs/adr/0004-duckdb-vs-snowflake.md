# ADR 0004: DuckDB locally, Snowflake as the parity target

- **Status:** Accepted
- **Date:** 2026-10-23
- **Deciders:** Breakout maintainer

## Context

The dataset is under 100 MB. The product has one user and a laptop. Query latency matters for the dashboard, and cost matters because the project should be free to run.

A cloud warehouse adds concurrency, governance, and multi-team access. It also adds a bill, credentials, and a slower local loop. The repo already has a Snowflake/Snowpark path from the legacy pipeline.

## Decision

Use **DuckDB** for local development, CI, and the public demo. Keep the dbt models ANSI and add a **Snowflake** target for parity testing when credentials are available. Benchmark the same workload before claiming one is faster.

## Alternatives considered

- **Snowflake for everything:** Strong enterprise signal, but unnecessary for a single-user 100 MB dataset and adds cost/credentials to every contribution.
- **BigQuery:** Similar tradeoff; serverless pricing is harder to predict for a portfolio.
- **Postgres:** Great for transactions, not the best analytical scan engine for this workload.
- **Spark:** Operationally heavy for a laptop-sized dataset.

## Consequences

**Positive**

- $0 local compute.
- Warm dashboard queries are 12-19 ms; a 10M-row synthetic scan is ~35 ms.
- CI can run the full pipeline on every PR.
- The dbt SQL remains portable.

**Negative**

- No concurrency or row-level governance.
- A single machine caps scale.
- The Snowflake parity path is not yet exercised in CI.
- DuckDB's optimizer and SQL dialect differ from Snowflake in edge cases.

## Revisit when

- Multiple users or teams need concurrent access.
- The data outgrows a single node or the joins no longer fit in memory.
- Governance, sharing, or compliance requires a warehouse.
- The target employer standardizes on Snowflake, BigQuery, or Databricks.
