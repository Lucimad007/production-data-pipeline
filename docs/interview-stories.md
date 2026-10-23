# Interview story bank

Eight stories from the Breakout build, mapped to common loops. Each story has a 60-second version and a likely follow-up.

## 1. Quota-aware ingestion

**Loop:** coding, system design, API integration.

**Situation:** The YouTube Data API gives 10,000 quota units per day. `search.list` costs 100 units; most list endpoints cost 1. A naive ingestion loop can burn the day's budget in a few calls.

**Action:** I used the uploads playlist instead of search, batched 50 video IDs per `videos.list` call, added retries with jitter and `Retry-After`, and put every call behind a SQLite quota ledger with an 80% daily budget. The ledger refuses a call before it is made, so a bad config cannot quietly exhaust the quota.

**Result:** A 500-video refresh with comments for the top 20 costs 41 units, about 0.5% of the daily budget. The client is tested for 500-then-200, 429 with `Retry-After`, and a 403 that must not retry.

**60-second version:** "I treated quota as a first-class constraint. The pipeline pages the uploads playlist, batches 50 IDs at a time, and refuses calls above 80% of the daily budget. A 500-video run costs 41 of 8,000 usable units."

**Follow-up:** "What happens if the quota resets mid-run?" The ledger is date-scoped; the scheduler checks the current UTC date and the budget before each call. A run that starts before midnight can continue after reset if the ledger sees the new date. In production I would pin the run to a quota window and make the reset explicit.

## 2. Idempotent replay and the raw landing

**Loop:** reliability, data engineering fundamentals.

**Situation:** API responses change, parsers have bugs, and the public API cannot reconstruct historical view counts. Re-fetching is expensive and sometimes impossible.

**Action:** I wrote every response to an immutable JSON landing zone before parsing. The file is keyed by a hash of the request, fetch time, and payload. Bronze writes are idempotent on natural keys, and batches are deduplicated before insert. A `breakout ingest` run writes raw files first, then upserts bronze.

**Result:** Replaying the same collection leaves row counts unchanged. A parser fix can replay the raw layer without spending quota. The raw landing also made the DuckLake path incident a connection bug rather than a data-loss event.

**60-second version:** "Raw first, parse second. Every response lands with hashes, and every bronze write is idempotent. I can replay a bad parser or a failed load without touching the API."

**Follow-up:** "How do you deduplicate?" Natural keys: `(channel_id, snapshot_at)`, `video_id`, `(video_id, snapshot_at)`, `comment_id`, and `response_id` for raw envelopes. Each batch is deduped before the delete/insert, so a batch with duplicate keys cannot create duplicates.

## 3. The DuckLake path incident

**Loop:** debugging, ownership, postmortem.

**Situation:** The first dbt build after ingestion failed before any model ran. DuckLake said the `DATA_PATH` did not match the catalog. The paths looked equivalent.

**Action:** I reproduced it, read the exact error, and found that DuckLake compares the path string, not the resolved directory. The Python loader used an absolute path; the dbt profile used a relative one. I added a `breakout build` command that normalizes all three paths to absolute before invoking dbt, and documented the constraint in an ADR.

**Result:** The build went from blocked to 37/37. The fix is now the supported entry point, and the CI fixture exercises a clean build. I wrote a postmortem with the timeline, root cause, and prevention.

**60-second version:** "DuckLake treats the data path as part of the catalog contract. Absolute in Python, relative in dbt, so it refused to attach. I made the CLI normalize paths and wrote the postmortem. The lesson is to make the safe path the easy path."

**Follow-up:** "What would you do differently?" I would add an integration test for the user-facing build entry point before the first live run, not just storage tests. The storage tests passed because they used one path convention; the bug lived at the boundary between two entry points.

## 4. Age-adjusted performance instead of raw views

**Loop:** analytics engineering, data modeling, product thinking.

**Situation:** The obvious metric, views per day, punishes old videos and rewards recent uploads. A two-year-old evergreen video can be more valuable than a two-day-old spike, but the raw metric says the opposite.

**Action:** I bucketed videos by age and computed a robust z-score of `log1p(views)` against the channel's median and MAD for the same bucket. I used that score for the leaderboard, topics, and publish timing. I explicitly rejected raw views/day for the timing and topic "lift" because it biased toward recent uploads.

**Result:** 68 of 500 videos were breakouts and 30 were underperformers at the first snapshot. The top videos were money/business content, and the timing mart showed Friday 14:00 UTC as the strongest cell with 8 videos. The score is explainable and robust to outliers.

**60-second version:** "Views per day is age-biased. I compare log views to the channel's own median for the same age bucket, using a robust z-score. That is the metric behind the leaderboard, topics, and timing."

**Follow-up:** "Why not a model?" A learned model needs a backtest and a baseline. The robust z-score is the baseline; a model has to beat it before it replaces it. That is the next step, not the first step.

## 5. SLO health caught stale data

**Loop:** reliability, ownership, operations.

**Situation:** After the first day, `breakout health` reported freshness at 11.7 hours against a 6-hour SLO. The pipeline had not run since the previous session.

**Action:** I treated the failure as a real signal, not a nuisance. I re-ran ingestion, rebuilt the marts, and confirmed all 10 checks were green. The health command exits non-zero on error-severity failures and supports JSON for automation.

**Result:** Freshness went to 0.0 hours, quota usage was 41/8,000, coverage was 507/507, and dbt had 0 failures. The same checks now run in the dashboard and in CI against the fixture.

**60-second version:** "The health check caught an 11.7-hour freshness breach. I re-ran ingestion and dbt, and all ten checks went green. The point is that the pipeline can tell you it is stale before a dashboard misleads someone."

**Follow-up:** "What is missing for production?" Alerting and a rolling freshness distribution. The current check uses the latest snapshot; production should use a p95 over a window and page on-call.

## 6. Dashboard visual QA

**Loop:** product engineering, quality, attention to detail.

**Situation:** The first dashboard screenshot looked broken: five metric cards wrapped into unreadable values, and the remaining cards rendered as raw HTML. A second issue appeared on the video page: two snapshots 23 minutes apart produced a zoomed line that looked like a flat trend.

**Action:** I inspected the rendered app in headless Chrome, not just the unit tests. I replaced the Streamlit columns with a CSS grid, collapsed the card HTML to one line so Markdown would not treat it as a code block, and suppressed the snapshot curve when the interval or span was too small to be meaningful.

**Result:** The five pages render cleanly at 1440px. The dashboard test runs the app through Streamlit's `AppTest` so an uncaught exception fails CI.

**60-second version:** "Tests said the app rendered; the screenshot said it looked broken. I fixed the Markdown and chart-scale issues and added a headless browser check to the workflow."

**Follow-up:** "How do you prevent visual regressions?" A screenshot diff in CI is the next step. The AppTest catches exceptions, not layout.

## 7. Batch vs streaming

**Loop:** system design, architecture.

**Situation:** The project is a data pipeline, and the tempting move is to add Kafka and Flink because they are on job descriptions. But the source is a pull API and the product answers daily questions.

**Action:** I wrote an ADR that chooses daily micro-batches, documents the alternatives, and states when to revisit. The ingestion asset is intentionally one unit because the API calls share a quota budget and a session.

**Result:** One process, one schedule, one quota ledger, and a local setup that runs on Windows without Docker. The pipeline is honest about its 6-hour freshness SLO instead of pretending to be real-time.

**60-second version:** "The source is polled, so streaming would be theater. I chose micro-batches, wrote the ADR, and documented the exact conditions that would make me add a stream."

**Follow-up:** "When would you add Kafka?" When there is a real event source, a sub-minute SLA, or multiple consumers that need the same event log. Then the design changes: event-time watermarks, exactly-once sinks, schema registry, and replay.

## 8. Schema drift and quarantine

**Loop:** data quality, reliability, API integration.

**Situation:** A video payload can be missing a title, a count can be hidden, a video can be deleted between discovery and stats fetch, and a new field can appear without warning.

**Action:** I put Pydantic contracts at the boundary. Malformed items go to `bronze.quarantine` with a reason and payload hash instead of being dropped. Hidden counts become null, not zero. Missing videos are tolerated. The raw envelope is always preserved.

**Result:** A malformed item in a 50-video batch does not fail the whole run. The quarantine is a warning in `breakout health`, so it is visible without blocking a refresh. The runbook explains how to review it and replay after a contract fix.

**60-second version:** "A bad row should not drop the batch, and it should not disappear. It goes to quarantine with a reason and the raw payload stays on disk. Hidden counts are null, not zero."

**Follow-up:** "What about a new required field?" The contract test fails, the raw payload is preserved, and the fix is a parser change plus a replay. No API call is needed.

## Loop map

| Loop | Stories |
|---|---|
| Coding / Python | 1, 2, 8 |
| SQL / modeling | 4 |
| System design | 1, 7, 8 |
| Reliability / operations | 2, 3, 5 |
| Product / quality | 4, 6 |
| Incident / ownership | 3, 5 |
| AI / next step | 4 follow-up, 5 follow-up |
