# 3-minute demo script

The goal is not to show every feature. It is to show that you can frame a problem, build the pipeline, operate it, and explain the tradeoffs.

## Before recording

- [ ] `uv run breakout health` is green.
- [ ] `uv run breakout build` has run in the last day.
- [ ] Dagster is running: `uv run dagster dev -m breakout.definitions`.
- [ ] Dashboard is running: `uv run breakout dashboard`.
- [ ] Close Slack, email, and unrelated browser tabs.
- [ ] Terminal font at 16-18 px; light theme or a clean dark theme.
- [ ] Hide `.env` and any tokens.
- [ ] Browser at 1440x900 or 1920x1080; zoom 100%.
- [ ] One dry run without recording to check timing.

## 0:00-0:20 — The problem

**Show:** the Overview page.

**Say:**

> Most creator dashboards show views. That is not a decision. I built Breakout to answer a better question: which videos actually broke out for this channel, and what should be published next? It is also a reliability project: every number has to be reproducible and every failure has to be visible.

## 0:20-0:50 — Ingestion and quota

**Show:** terminal.

```powershell
uv run breakout status
uv run breakout ingest --channel AlexHormozi --max-videos 500 --comment-videos 20
```

**Say:**

> YouTube gives you 10,000 quota units a day. Search costs 100; the playlist path costs 1. The client pages uploads, batches 50 video IDs per call, retries 5xx and 429 with backoff, and records every unit in a quota ledger. This run pulls 500 videos and comments for the top 20 for 41 units.

Point at the output:

```text
videos=500 comments=400 quarantined=0
quota_units=41
raw_files=41
```

**Say:**

> Every response is written to the raw landing before parsing. That is the replay and audit layer.

## 0:50-1:20 — dbt and lineage

**Show:** terminal.

```powershell
uv run breakout build
```

**Say:**

> dbt stages bronze, snapshots the video dimension, and builds the gold marts. The key metric is not raw views per day; it is an age-adjusted robust z-score against the channel's own baseline for the same age bucket. That stops a two-year-old video from looking bad just because it is old.

**Show:** Dagster UI at `localhost:3000`.

**Say:**

> Dagster owns the operating surface: ingest, dbt, and pipeline health as assets, with checks and a daily schedule. The asset graph is the lineage a reviewer can read without opening the code.

## 1:20-2:00 — The product

**Show:** Overview page. Hover a breakout point.

**Say:**

> Each dot is a video. Green is a breakout, gray is typical, coral is an underperformer. The score is relative to the channel and the age bucket. The leaderboard is the "what worked" list; the topics page explains the pattern.

**Show:** Video deep dive.

**Say:**

> This is the "why" view. It compares the video with the channel baseline, shows its snapshot history, and surfaces the top comments. When the two snapshots are too close together, the app suppresses the curve instead of drawing a misleading line.

**Show:** Topics and Timing.

**Say:**

> Topics are keyword-derived and suppressed below three videos. Timing is observational: Friday at 14:00 looks strong here, but publish time is correlated with topic and audience timezone. I label it as a signal, not a causal lever.

## 2:00-2:30 — Reliability

**Show:** Health page and terminal.

```powershell
uv run breakout health
```

**Say:**

> This is the part I care about most. Ten SLO checks: freshness, quota, quarantine, mart coverage, duplicate keys, null scores, and dbt failures. It caught stale data at 11.7 hours, I re-ran ingestion, and it went green. The runbook covers the four failure modes.

Point at the health page's "Live checks" and the dbt card.

## 2:30-2:50 — Incident story

**Show:** `docs/postmortem-001-ducklake-path.md` or just talk.

**Say:**

> The first dbt build failed because DuckLake stores the data path string and the loader used an absolute path while dbt used a relative one. The fix was to make the CLI normalize paths and make the safe path the easy path. The raw landing meant there was no data loss, and the postmortem documents the detection, root cause, and prevention.

## 2:50-3:00 — Close

**Show:** README or repo.

**Say:**

> The stack is DuckDB and DuckLake locally, dbt for the models, Dagster for orchestration, Streamlit for the product, and a documented Iceberg/Snowflake path for production. The README has the benchmark, the ADRs, the runbook, and the limitations. The next step is a governed metric registry and an MCP analyst, not raw text-to-SQL.

## If something fails live

- If quota is exhausted, show `breakout health` and the quota ledger; that is a feature, not a bug.
- If the dashboard has no data, run `breakout ingest` + `breakout build` and refresh.
- If Dagster is not running, skip the UI and show the definitions file and the check output.
- Never debug a live failure silently for more than 20 seconds. Narrate the diagnosis.
