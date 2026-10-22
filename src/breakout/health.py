"""SLO checks shared by the CLI and the dashboard."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

from breakout.config import PROJECT_ROOT, Settings, get_settings
from breakout.pipeline import bronze_counts, latest_snapshot, quota_status
from breakout.storage import Lakehouse


@dataclass(frozen=True)
class SloCheck:
    name: str
    observed: str
    target: str
    passed: bool
    severity: str = "error"


def _hours_since(value: str | None) -> float | None:
    if not value:
        return None
    stamp = pd.Timestamp(value).to_pydatetime()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return float((datetime.now(UTC) - stamp).total_seconds() / 3600)


def evaluate_slos(settings: Settings | None = None) -> list[SloCheck]:
    settings = settings or get_settings()
    counts = bronze_counts(settings)
    checks = [
        SloCheck(
            "bronze_videos_present",
            f"{counts['videos']}",
            "> 0",
            counts["videos"] > 0,
        ),
        SloCheck(
            "snapshots_present",
            f"{counts['video_snapshots']}",
            "> 0",
            counts["video_snapshots"] > 0,
        ),
        SloCheck(
            "comments_present",
            f"{counts['comments']}",
            "> 0",
            counts["comments"] > 0,
        ),
    ]

    age = _hours_since(latest_snapshot(settings))
    checks.append(
        SloCheck(
            "freshness_hours",
            f"{age:.1f}" if age is not None else "missing",
            "< 6",
            age is not None and age < 6,
        )
    )

    quota = quota_status(settings)
    checks.append(
        SloCheck(
            "quota_used",
            f"{quota.used}/{quota.budget}",
            "<= budget",
            quota.used <= quota.budget,
        )
    )
    checks.append(
        SloCheck(
            "quarantine_empty",
            f"{counts['quarantine']}",
            "0",
            counts["quarantine"] == 0,
            severity="warn",
        )
    )

    try:
        with Lakehouse(settings) as lake:
            frame = lake.query_df(
                """
                select
                  (select count(*) from lake.gold.mart_video_performance) as mart_rows,
                  (select count(*) from lake.bronze.videos) as bronze_rows,
                  (select count(*) - count(distinct video_id)
                     from lake.gold.mart_video_performance) as duplicate_keys,
                  (select count(*) from lake.gold.mart_video_performance
                     where breakout_score is null) as null_scores
                """
            )
        row = frame.iloc[0]
        bronze_rows = int(row["bronze_rows"])
        mart_rows = int(row["mart_rows"])
        coverage = mart_rows / bronze_rows if bronze_rows else 0.0
        checks.extend(
            [
                SloCheck(
                    "mart_coverage",
                    f"{mart_rows}/{bronze_rows}",
                    "> 95%",
                    bronze_rows > 0 and coverage > 0.95,
                ),
                SloCheck(
                    "mart_keys_unique",
                    f"{int(row['duplicate_keys'])} duplicates",
                    "0",
                    int(row["duplicate_keys"]) == 0,
                ),
                SloCheck(
                    "breakout_scores_present",
                    f"{int(row['null_scores'])} nulls",
                    "0",
                    int(row["null_scores"]) == 0,
                ),
            ]
        )
    except Exception as exc:  # noqa: BLE001 - health must report a missing mart, not crash
        checks.append(SloCheck("mart_checks_available", type(exc).__name__, "no error", False))

    run_results = PROJECT_ROOT / "dbt_project" / "target" / "run_results.json"
    if not run_results.exists():
        checks.append(
            SloCheck("dbt_results_present", "missing", "present", False, severity="warn")
        )
    else:
        try:
            payload = json.loads(run_results.read_text(encoding="utf-8"))
            results = payload.get("results", [])
            failed = sum(
                1 for result in results if result.get("status") in {"error", "fail"}
            )
            checks.append(SloCheck("dbt_failures", f"{failed}", "0", failed == 0))
        except (OSError, json.JSONDecodeError):
            checks.append(
                SloCheck("dbt_results_readable", "unreadable", "readable", False, severity="warn")
            )

    return checks


def failing_checks(checks: list[SloCheck]) -> list[SloCheck]:
    return [check for check in checks if not check.passed and check.severity == "error"]
