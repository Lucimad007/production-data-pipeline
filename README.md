# Production data pipeline

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

## Channel video statistics

Collect every public upload for a channel, with duration and lifetime view, like, and comment counts. The channel defaults to Alex Hormozi:

```powershell
python -m pipeline.video_stats
```

Limit the run to the newest videos, or choose another handle:

```powershell
python -m pipeline.video_stats --channel AlexHormozi --max-videos 50
```

Rows are upserted into the `video_stats` table in `data/output/youtube.db`, so rerunning refreshes the counts. To load the same rows into Snowflake, fill in the `SNOWFLAKE_*` values and use:

```powershell
python -m pipeline.video_stats --destination snowflake
```

The Snowflake table is `YOUTUBE_VIDEO_STATS`.

## Test

```bash
python -m unittest tests.test_pipeline tests.test_youtube tests.test_snowflake tests.test_video_stats
```
