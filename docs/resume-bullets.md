# Resume and LinkedIn bullets

Use the numbers from the current snapshot; re-run `scripts/benchmark.py` before submitting so they are current.

## Project line

**Breakout — creator growth intelligence lakehouse** | [GitHub](https://github.com/Lucimad007/production-data-pipeline)
Local-first data product that ingests public YouTube data, models creator performance, and exposes an operational SLO surface. Python, DuckDB, DuckLake, dbt, Dagster, Streamlit, GitHub Actions.

## Bullets

- Built an end-to-end creator intelligence lakehouse ingesting 500+ videos, 1,500+ snapshots, and 400+ comments from the YouTube Data API, with typed Pydantic contracts, retries, and an immutable raw landing zone.
- Designed a quota-aware ingestion client that pages the uploads playlist and batches 50 video IDs per call, cutting a 500-video refresh with comments to 41 of 8,000 usable daily units; added a SQLite ledger that refuses calls above the 80% budget.
- Made every bronze write idempotent on natural keys and replayable from raw JSON; verified that replaying the same collection leaves row counts unchanged and that malformed items land in a quarantine table instead of being dropped.
- Modeled age-adjusted performance in dbt with a robust z-score over `log1p(views)` by channel and age bucket, replacing raw views/day to remove recency bias; built video, channel, topic, publish-timing, and snapshot-delta marts.
- Orchestrated `ingest -> dbt -> health` as Dagster assets with asset checks, run metadata, and a daily schedule; reduced the operating surface to one command and one visible lineage graph.
- Built a five-page Streamlit product (overview, video deep dive, topics, timing, health) with a custom visual system, cached queries, and honest empty states; warm dashboard queries run in 12–19 ms.
- Added a 10-check SLO evaluator (`breakout health`) for freshness, quota, quarantine, mart coverage, key uniqueness, null scores, and dbt failures; the check caught an 11.7-hour freshness breach and returned green after recovery.
- Added a 37-node dbt build (10.5 s), 40 automated tests, a deterministic CI fixture, and GitHub Actions across Ubuntu and Windows; documented six ADRs, a postmortem, a runbook, and a 3-minute demo script.

## Short version for LinkedIn

> I built Breakout, a local-first creator intelligence lakehouse. It ingests YouTube data with quota-aware scheduling, preserves every raw response, models age-adjusted breakout performance in dbt, orchestrates the pipeline in Dagster, and exposes a five-page Streamlit product plus a 10-check SLO health command. The build includes 40 tests, a deterministic CI fixture, six ADRs, a postmortem, and a runbook. Warm dashboard queries: 12–19 ms. Local compute cost: $0.

## Skills to list

**Languages:** Python, SQL
**Data:** DuckDB, DuckLake, Apache Iceberg (concepts and production path), Parquet, dbt, dimensional modeling, SCD2, incremental models, data quality tests
**Platform:** Dagster, GitHub Actions, Docker (optional), Windows and Linux CI
**AI:** metric registry design, MCP (next), RAG and eval harness (planned)
**Engineering:** Pydantic, httpx, retries/backoff, idempotency, quota management, observability, ADRs, postmortems

## What to emphasize in interviews

- **Constraints over tools:** quota, freshness, cost, and the absence of historical stats drove the design.
- **Reliability over demos:** raw landing, idempotency, quarantine, SLOs, runbook.
- **Honest metrics:** age-adjusted score, small-sample suppression, observational language.
- **Tradeoffs:** batch vs streaming, DuckLake vs Iceberg, Dagster vs Airflow, DuckDB vs Snowflake.
- **Ownership:** the incident, the fix, the postmortem, and the prevention.

## What not to claim

- Do not call it "production-scale." It is a portfolio-scale product with production-shaped practices.
- Do not claim real-time. The source is polled; freshness is measured in hours.
- Do not claim a Snowflake benchmark until the parity path is actually run.
- Do not claim the AI layer is built. It is a documented next step.
