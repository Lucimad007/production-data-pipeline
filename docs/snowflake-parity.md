# Snowflake parity

**Status:** Portability layer ready; parity run blocked on credentials.

The `.env` Snowflake values in this workspace are placeholders, so I did not run a Snowflake build or claim a cost number. The DuckDB path is fully exercised; the Snowflake path is prepared and documented.

## What is ready

- A `snowflake` target in `dbt_project/profiles.yml` driven by environment variables.
- Dialect macros in `dbt_project/macros/dialect.sql`:
  - `date_diff_compat`: DuckDB `date_diff`, Snowflake `datediff`.
  - `regexp_matches_compat`: DuckDB `regexp_matches`, Snowflake `regexp_like`.
- The same dbt models and tests for both targets.
- Optional dependencies: `uv sync --extra snowflake` installs `dbt-snowflake` and `snowflake-snowpark-python`.
- The existing `pipeline/snowflake_load.py` shows the Snowpark merge pattern for the legacy tables.

## What is not done

- A bronze loader that copies the DuckLake bronze tables into a Snowflake `BRONZE` schema.
- A real `dbt build --target snowflake` run and row-level parity check.
- A nightly Snowflake CI job with a cost cap.
- Snowflake Iceberg tables (depends on account and region support).

## How to run it

1. Fill the `SNOWFLAKE_*` values in `.env`.
2. Install the optional dependencies:

   ```powershell
   uv sync --extra snowflake
   ```

3. Load the bronze tables. The outline is:

   ```python
   import os
   from snowflake.connector import connect
   from snowflake.connector.pandas_tools import write_pandas
   from breakout.storage import Lakehouse

   conn = connect(
       account=os.environ["SNOWFLAKE_ACCOUNT"],
       user=os.environ["SNOWFLAKE_USER"],
       password=os.environ["SNOWFLAKE_PASSWORD"],
       warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
       database=os.environ["SNOWFLAKE_DATABASE"],
       schema="BRONZE",
       role=os.environ["SNOWFLAKE_ROLE"],
   )
   with Lakehouse() as lake:
       for table in ["channels", "videos", "video_snapshots", "comments"]:
           frame = lake.query_df(f"select * from lake.bronze.{table}")
           write_pandas(conn, frame, table.upper(), schema="BRONZE", auto_create_table=True)
   conn.close()
   ```

   This is an outline, not a tested script. The production version should stage Parquet in S3/GCS and use `COPY INTO`, not row-by-row inserts.

4. Build the Snowflake target:

   ```powershell
   uv run dbt build --project-dir dbt_project --profiles-dir dbt_project --target snowflake
   ```

5. Compare parity:

   ```sql
   select count(*) from SILVER.DIM_VIDEO;
   select count(*) from GOLD.MART_VIDEO_PERFORMANCE;
   select video_id, breakout_score from GOLD.MART_VIDEO_PERFORMANCE order by breakout_score desc limit 10;
   select topic, median_breakout_score from GOLD.MART_TOPIC_PERFORMANCE order by 2 desc;
   ```

   The row counts and the top-10 scores should match the DuckDB target within floating-point tolerance.

## Cost model

| Item | Assumption |
|---|---|
| Warehouse | XS, auto-suspend after 60 seconds |
| Credits | 1 credit/hour while running |
| Parity run | < 5 minutes |
| List price | ~$2–4 per credit depending on edition and region |
| Estimated parity cost | < $0.50 |
| Storage | Negligible for < 1 GB |

Use a dedicated `BREAKOUT_WH` warehouse, a `BREAKOUT_ROLE`, and `query_tag = breakout_dbt` so the cost is attributable. Do not use a shared production warehouse for a parity test.

## Decision

Keep DuckDB as the local and demo engine. Use Snowflake when concurrency, governance, or a team standard justifies it. See [ADR 0004](adr/0004-duckdb-vs-snowflake.md).

## Why this is honest

A parity claim without a run is just a diagram. This document separates what is tested (DuckDB, 37/37) from what is prepared (Snowflake target and macros) from what is blocked (credentials). The next person can finish it without reverse-engineering the intent.
