# Breakout runbook

The pipeline is small, but the failure modes are real. This runbook covers the four that matter and the commands to diagnose them.

## SLOs

| SLO | Target | Check |
|---|---|---|
| Bronze videos present | > 0 | `breakout health` |
| Snapshots present | > 0 | `breakout health` |
| Comments present | > 0 | `breakout health` |
| Freshness | < 6 hours | `breakout health` |
| Quota | <= 80% of daily budget | `breakout health` |
| Quarantine | 0 items | `breakout health` |
| Mart coverage | > 95% of bronze videos | `breakout health` |
| Mart keys | 0 duplicates | `breakout health` |
| Breakout scores | 0 nulls | `breakout health` |
| dbt failures | 0 | `breakout health` |

Run the full check:

```powershell
uv run breakout health
uv run breakout health --json
```

The command exits non-zero only on error-severity failures. Warnings (quarantine, missing dbt artifacts) are reported but do not fail the run.

## 1. Quota exhausted

**Symptoms**

- Ingestion exits with code 3 and `Quota budget reached`.
- YouTube returns 403 with `quotaExceeded`.
- `breakout health` shows `quota_used` above budget.

**Diagnose**

```powershell
uv run breakout status
uv run python -c "import sqlite3; c=sqlite3.connect('data/quota.sqlite'); print(c.execute('select endpoint, sum(units) from quota_usage where substr(used_at,1,10)=date(\"now\") group by 1 order by 2 desc').fetchall())"
```

**Mitigate**

- Wait for the YouTube quota reset at midnight Pacific Time.
- Reduce `--max-videos` or `--comment-videos` for the next run.
- Lower `quota_budget_pct` in `.env` if the budget is being spent too aggressively.

**Prevent**

- The ledger refuses calls above 80% of the daily budget.
- `search.list` is not in the hot path; it costs 100 units versus 1 for the playlist path.
- Snapshot only the videos that matter for the next decision, not the entire back catalog every hour.

## 2. dbt test failure

**Symptoms**

- `uv run breakout build` exits non-zero.
- The last line shows `ERROR=...` or a failing test name.
- Dagster `dbt_models` fails with `dbt build failed`.

**Diagnose**

```powershell
uv run python -c "import json; d=json.load(open('dbt_project/target/run_results.json')); print([(r['unique_id'], r['status']) for r in d['results'] if r['status'] not in ('success','pass')])"
```

Then query the failing model directly:

```powershell
uv run python -c "from breakout.storage import Lakehouse; l=Lakehouse(); print(l.query_df('select * from lake.gold.mart_video_performance limit 5'))"
```

**Mitigate**

- Fix the model or the contract. Do not silence a blocking test.
- If the failure is caused by bad source rows, inspect `lake.bronze.quarantine` and the raw envelope.
- Re-run `uv run breakout build` after the fix.

**Prevent**

- The CI fixture runs the same dbt tests on every PR.
- Source freshness and schema tests run before the marts.
- A failing test blocks the merge.

## 3. Schema drift or quarantined rows

**Symptoms**

- Ingestion prints `quarantined=N` where N > 0.
- `breakout health` shows `quarantine_empty` as WARN.
- A new API field appears, or a required field disappears.

**Diagnose**

```powershell
uv run python -c "from breakout.storage import Lakehouse; l=Lakehouse(); print(l.query_df('select * from lake.bronze.quarantine order by ingested_at desc'))"
```

The raw response is preserved at:

```text
data/raw/endpoint=videos/dt=YYYY-MM-DD/<response_id>.json
```

**Mitigate**

- Update the Pydantic contract in `src/breakout/contracts.py`.
- Replay the raw envelope through the parser; no API call is needed.
- Add a regression fixture to `tests/`.

**Prevent**

- Contract tests run in CI.
- Unknown fields are allowed but logged; missing required fields are quarantined.
- Raw landing is immutable, so a parser fix never requires a re-fetch.

## 4. Stale data

**Symptoms**

- `breakout health` shows `freshness_hours` FAIL.
- Dagster shows a missed or failed schedule.
- The dashboard header shows an old snapshot date.

**Diagnose**

```powershell
uv run breakout health
uv run dagster asset materialize --select "ingest+" -m breakout.definitions
```

**Mitigate**

- Re-run the asset graph manually.
- If the API is failing, check the raw landing and the last successful run metadata.
- If quota is exhausted, follow section 1.

**Prevent**

- The daily schedule runs at 06:00 UTC.
- Asset checks surface bronze, quota, and mart failures.
- In production, alert on freshness and failed runs; this repo's health command is the local equivalent.

## Recovery checklist

1. Run `uv run breakout health`.
2. Identify whether the failure is source, quota, contract, or model.
3. Prefer replay from raw over re-fetching from the API.
4. Fix the cause, not the symptom.
5. Re-run `uv run breakout build`.
6. Confirm `uv run breakout health` is green.
7. Record what happened, what was changed, and what prevents a repeat.
