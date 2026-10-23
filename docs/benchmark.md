# Benchmark

These are warm-cache, single-machine numbers from the local Breakout stack. They are useful for regression detection and honest portfolio claims, not for comparing unrelated systems.

## Environment

| Item | Value |
|---|---|
| OS | Windows 11 (10.0.26200) |
| CPU | 13th Gen Intel Core i5-13400F |
| RAM | 32 GB |
| Python | 3.12.9 |
| DuckDB | 2.0.0 |
| dbt | 1.12.6 |
| Orchestrator | Dagster 1.13.26 |
| Storage | DuckLake 1.x, SQLite catalog, local Parquet |

## Dataset

Snapshot from 2026-10-23:

| Item | Value |
|---|---|
| Bronze videos | 507 |
| Video snapshots | 1,510 |
| Comments | 423 |
| Video performance rows | 507 |
| DuckLake size | 2.5 MB |
| Raw landing size | 7.1 MB |
| Quota used / budget | 41 / 8,000 units |

## Results

| Metric | Value |
|---|---|
| `dbt build` (37 nodes, startup + run) | 10.5 s |
| Cold query: channel overview (attach + query) | 189.3 ms |
| Cold query: breakout leaderboard (20) | 316.2 ms |
| Cold query: topic performance | 332.4 ms |
| Cold query: publish timing | 334.7 ms |
| Warm query: channel overview | 13.8 ms |
| Warm query: breakout leaderboard (20) | 19.4 ms |
| Warm query: topic performance | 12.3 ms |
| Warm query: publish timing | 13.5 ms |
| Synthetic scan: 10M rows, group by 1,000 buckets | 34.6 ms |
| SLO evaluation (10 checks) | 996.7 ms |

## Methodology

- Query timings are the median of 5 runs.
- **Cold** means a new `Lakehouse` connection: DuckDB opens, loads the DuckLake extension, attaches the catalog, then runs the query. This is what a fresh dashboard query pays.
- **Warm** means one connection, repeated queries. The dashboard caches query results for 60 seconds, so warm numbers are the steady-state experience.
- The synthetic scan creates a 10M-row in-memory DuckDB table with `range(10_000_000)` and runs a group-by. It measures scan/aggregate throughput, not DuckLake I/O.
- `dbt build` includes dbt startup, parsing, seed, snapshot, 6 views, 5 tables, and 24 data tests.

## Interpretation

- The cold path is dominated by DuckLake attach (~190-330 ms), not by the query. The dashboard's 60-second cache hides that cost after the first load.
- Warm queries are 12-19 ms, which is fast enough for interactive filtering at this data size.
- A 10M-row scan in 35 ms is a credible local-DuckDB baseline. It is not a claim about 100M rows or concurrent users.
- Local compute cost is **$0**. The YouTube API is free within the daily quota.
- Snowflake has not been benchmarked yet. The same dbt models are the parity target; see ADR 0004.

## Reproduce

```powershell
uv run python scripts/benchmark.py
```

Measure the dbt build separately:

```powershell
$t = Measure-Command { uv run breakout build *> $null }
$t.TotalSeconds
```

## Caveats

- Laptop hardware; no concurrency.
- Warm cache; first-query latency is higher.
- The real dataset is small. The synthetic scan is a scale probe, not a production workload.
- No Snowflake or Spark comparison yet.
