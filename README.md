# Production data pipeline

## Breakout: creator growth intelligence (in progress)

Breakout is a local-first lakehouse for public YouTube data. It ingests a channel with quota-aware scheduling, preserves every API response in an immutable raw layer, writes bronze tables to DuckLake, and models creator performance with dbt.

```powershell
uv sync
uv run breakout ingest --channel AlexHormozi --max-videos 500
uv run breakout build
uv run breakout status
```

The current build includes ingestion, DuckLake bronze, dbt staging, an SCD2 `dim_video` snapshot, and gold marts for video performance, channel overview, publish timing, topic performance, and snapshot deltas. Dagster and the dashboard are the next workstreams.

See `docs/2026-flagship-plan.md` for the research brief, architecture, and 14-day plan, and epic #6 for the workstreams.

The legacy sample pipelines below remain runnable.

---

## Legacy: sample orders pipeline

Sample extract, transform, and load job for paid orders.

`data/sample_orders.csv` is the source. The pipeline drops refunds, blank customers, non-positive quantities, and duplicate order ids, then upserts the remaining lines into SQLite at `data/output/orders.db`.

## Run

```bash
python -m pipeline.run
```

Optional paths:

```bash
python -m pipeline.run --source data/sample_orders.csv --database data/output/orders.db
```

## YouTube search

Uses a YouTube Data API v3 key from `.env` (see `.env.example`). `.env` is gitignored.

```powershell
python -m pipeline.youtube --query "data pipeline" --max-results 5
```

Results land in `data/output/youtube.db`.

To load the same rows into Snowflake, fill in the `SNOWFLAKE_*` values in `.env`, install dependencies, and choose that destination:

```powershell
pip install -e .
python -m pipeline.youtube --destination snowflake --query "data pipeline" --max-results 5
```

The job opens a Snowpark session, creates `YOUTUBE_VIDEOS`, and merges a DataFrame on `VIDEO_ID`.

## Test

```bash
python -m unittest tests.test_pipeline tests.test_youtube tests.test_snowflake
```
