"""Measure the local Breakout stack and print a Markdown table.

The numbers are warm-cache, single-machine numbers. They are useful for
detecting regressions and for honest portfolio claims, not for comparing
unrelated systems.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable
from pathlib import Path

import duckdb

from breakout.config import get_settings
from breakout.health import evaluate_slos
from breakout.pipeline import bronze_counts, mart_counts, quota_status
from breakout.storage import Lakehouse


def median_ms(fn: Callable[[], object], repeats: int = 5) -> float:
    timings: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        timings.append((time.perf_counter() - started) * 1000)
    return statistics.median(timings)


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def main() -> None:
    settings = get_settings()
    counts = bronze_counts(settings)
    marts = mart_counts(settings)
    quota = quota_status(settings)

    queries = {
        "channel overview": "select * from lake.gold.mart_channel_overview",
        "breakout leaderboard (20)": """
            select title, breakout_score, view_count
            from lake.gold.mart_video_performance
            order by breakout_score desc
            limit 20
        """,
        "topic performance": (
            "select * from lake.gold.mart_topic_performance order by median_breakout_score desc"
        ),
        "publish timing": (
            "select * from lake.gold.mart_publish_timing order by median_breakout_score desc"
        ),
    }

    synthetic = duckdb.connect()
    synthetic.execute(
        """
        create table synth as
        select i as id, i % 1000 as bucket, random() as value
        from range(10_000_000) as t(i)
        """
    )

    def synthetic_scan() -> object:
        return synthetic.execute(
            "select bucket, count(*), avg(value) from synth group by 1"
        ).fetchall()

    rows: list[tuple[str, str]] = [
        ("Bronze videos", f"{counts['videos']:,}"),
        ("Video snapshots", f"{counts['video_snapshots']:,}"),
        ("Comments", f"{counts['comments']:,}"),
        ("Quarantined items", f"{counts['quarantine']:,}"),
        ("Video performance rows", f"{marts['mart_video_performance']:,}"),
        ("dbt models and tests", "37 nodes"),
        ("SLO checks", "10"),
        ("Quota used / budget", f"{quota.used:,} / {quota.budget:,}"),
        ("DuckLake size", f"{directory_size(settings.ducklake_data) / 1_048_576:.1f} MB"),
        ("Raw landing size", f"{directory_size(settings.raw_dir) / 1_048_576:.1f} MB"),
        ("Dashboard pages", "5"),
    ]

    for name, sql in queries.items():
        def cold(sql: str = sql) -> object:
            with Lakehouse(settings) as lake:
                return lake.query_df(sql)

        rows.append((f"Cold query (attach + query): {name}", f"{median_ms(cold):.1f} ms"))

    with Lakehouse(settings) as lake:
        for name, sql in queries.items():
            rows.append(
                (
                    f"Warm query: {name}",
                    f"{median_ms(lambda sql=sql: lake.query_df(sql)):.1f} ms",
                )
            )

    rows.append(("Synthetic scan: 10M rows", f"{median_ms(synthetic_scan, repeats=3):.1f} ms"))
    rows.append(("SLO evaluation", f"{median_ms(lambda: evaluate_slos(settings), repeats=3):.1f} ms"))

    print("| Metric | Value |")
    print("|---|---|")
    for name, value in rows:
        print(f"| {name} | {value} |")

    synthetic.close()


if __name__ == "__main__":
    main()
