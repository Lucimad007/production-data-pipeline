# Postmortem 001: DuckLake rejected the dbt build after the first ingest

- **Date:** 2026-10-22
- **Duration:** ~20 minutes
- **Severity:** SEV-3 (local build blocked, no data loss, no user impact)
- **Owner:** Breakout maintainer
- **Status:** Resolved

## Summary

The first `dbt build` after ingestion failed before running any model. DuckLake stores the `DATA_PATH` string in its catalog and rejects a different string, even when it resolves to the same directory. Ingestion created the catalog with an absolute path; the dbt profile passed a relative path. The pipeline was blocked until the paths were normalized.

## Impact

- No data was lost. The raw landing zone and bronze tables were intact.
- The local dbt build was blocked for about 20 minutes.
- No external users; the dashboard was not deployed yet.
- The failure was loud and immediate, not silent corruption.

## Timeline (UTC)

| Time | Event |
|---|---|
| 18:49 | First `dbt build` after the 500-video ingest fails during connection setup. |
| 18:49 | Error: `DATA_PATH parameter "data/lake\" does not match existing data path in the catalog "C:/.../data/lake/"`. |
| 18:50 | Confirmed the catalog and Parquet files existed; DuckDB could read the data directly. |
| 18:52 | Inspected `profiles.yml` and `storage.py`; found absolute vs relative path mismatch. |
| 18:55 | Re-ran dbt with absolute `BREAKOUT_*` environment variables; 37/37 nodes passed. |
| 19:00 | Added `breakout build`, which normalizes the paths before invoking dbt. |
| 19:05 | Re-ran `breakout build`; 37/37 passed. |
| 19:10 | Documented the behavior in the README and the DuckLake ADR. |

## Root cause

DuckLake treats the data path as part of the catalog contract. The Python storage layer wrote an absolute path:

```text
C:/Users/EXO/Desktop/repos/production-data-pipeline/data/lake
```

The dbt profile used a relative path:

```text
data/lake
```

DuckLake compared the strings, not the resolved directories, and refused to attach. The error message was accurate but easy to misread as a permissions problem.

## Detection

The failure happened on the first dbt connection, before any model ran. There was no partial write and no ambiguous state.

## Resolution

- Added `breakout build`, which sets `BREAKOUT_DUCKDB`, `BREAKOUT_DUCKLAKE_CATALOG`, and `BREAKOUT_DUCKLAKE_DATA` to absolute paths before invoking dbt.
- Kept the dbt profile env-var driven so CI and direct dbt runs can supply their own paths.
- The CI fixture uses relative paths consistently for both the seed script and dbt, which proves the second supported path.

## Prevention

- The CLI is the supported entry point. The README uses it.
- The DuckLake ADR documents the path-identity constraint.
- The CI fixture runs the same dbt build from a clean directory, so a path mismatch fails a PR.
- The postmortem is linked from the docs index.

## Lessons

1. **String identity is a contract.** A path that resolves to the same directory is not the same path to DuckLake.
2. **Make the safe path the easy path.** Two entry points with different path handling are a bug waiting to happen.
3. **Test the entry point, not only the library.** The storage tests passed; the user-facing build path did not exist yet.
4. **Raw landing paid off.** The incident was a connection bug, not a data loss event, because the source of truth was already on disk.

## Action items

- [x] Add `breakout build` with path normalization.
- [x] Document the constraint in ADR 0002.
- [x] Run dbt from a clean fixture in CI.
- [x] Add the incident to the interview story bank.
- [ ] Add a dedicated unit test for the path-normalization helper if the CLI grows more entry points.
