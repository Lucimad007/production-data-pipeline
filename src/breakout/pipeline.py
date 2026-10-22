"""Reusable pipeline operations shared by the CLI and Dagster assets."""

from __future__ import annotations

import os
from dataclasses import dataclass

from breakout.config import Settings
from breakout.storage import Lakehouse, RawLanding
from breakout.youtube import QuotaLedger, QuotaStatus, YouTubeClient


@dataclass(frozen=True)
class IngestResult:
    channel_title: str
    channel_id: str
    videos: int
    snapshots: int
    comments: int
    quarantined: int
    quota_used: int
    raw_files: int
    written: dict[str, int]
    bronze: dict[str, int]


def ingest_channel(
    settings: Settings,
    channel: str,
    *,
    max_videos: int = 0,
    comment_videos: int = 0,
    max_comments: int = 20,
) -> IngestResult:
    """Fetch a channel, write raw responses, and upsert bronze.

    The ingestion is intentionally one operation: the API calls share a quota
    budget and a session, and splitting them would duplicate requests. Dagster
    can still schedule and observe the whole unit.
    """
    with YouTubeClient(settings.youtube_api_key, settings=settings) as client:
        collection = client.collect(
            channel,
            max_videos=max_videos,
            comment_video_limit=comment_videos,
            max_comments_per_video=max_comments,
        )

    landing = RawLanding(settings.raw_dir)
    for envelope in collection.envelopes:
        landing.write(envelope)
    raw_files = len(collection.envelopes)

    with Lakehouse(settings) as lake:
        lake.write_api_responses(collection.envelopes)
        written = lake.write_collection(collection)
        bronze = lake.table_counts()

    return IngestResult(
        channel_title=collection.channel.title,
        channel_id=collection.channel.channel_id,
        videos=len(collection.videos),
        snapshots=len(collection.video_snapshots),
        comments=len(collection.comments),
        quarantined=len(collection.quarantined),
        quota_used=collection.quota_used,
        raw_files=raw_files,
        written=written,
        bronze=bronze,
    )


def build_models(settings: Settings) -> bool:
    """Run dbt with absolute lakehouse paths.

    DuckLake stores the data path in its catalog and rejects a relative path
    that resolves to the same directory but does not match the stored string.
    """
    os.environ["BREAKOUT_DUCKDB"] = str(settings.duckdb_path.resolve()).replace("\\", "/")
    os.environ["BREAKOUT_DUCKLAKE_CATALOG"] = str(
        settings.ducklake_catalog.resolve()
    ).replace("\\", "/")
    os.environ["BREAKOUT_DUCKLAKE_DATA"] = str(settings.ducklake_data.resolve()).replace(
        "\\", "/"
    )

    from dbt.cli.main import dbtRunner

    result = dbtRunner().invoke(
        [
            "build",
            "--project-dir",
            str(settings.dbt_project_dir),
            "--profiles-dir",
            str(settings.dbt_profiles_dir),
        ]
    )
    return bool(result.success)


def bronze_counts(settings: Settings) -> dict[str, int]:
    with Lakehouse(settings) as lake:
        return lake.table_counts()


def mart_counts(settings: Settings) -> dict[str, int]:
    with Lakehouse(settings) as lake:
        frame = lake.query_df(
            """
            select 'mart_video_performance' as mart, count(*) as rows
            from lake.gold.mart_video_performance
            union all
            select 'mart_channel_overview', count(*)
            from lake.gold.mart_channel_overview
            union all
            select 'mart_publish_timing', count(*)
            from lake.gold.mart_publish_timing
            union all
            select 'mart_topic_performance', count(*)
            from lake.gold.mart_topic_performance
            """
        )
    return {str(row.mart): int(row.rows) for row in frame.itertuples(index=False)}


def latest_snapshot(settings: Settings) -> str | None:
    with Lakehouse(settings) as lake:
        frame = lake.query_df(
            "SELECT MAX(snapshot_at) AS latest_snapshot FROM lake.bronze.video_snapshots"
        )
    if frame.empty or frame.loc[0, "latest_snapshot"] is None:
        return None
    return str(frame.loc[0, "latest_snapshot"])


def quota_status(settings: Settings) -> QuotaStatus:
    return QuotaLedger(settings.quota_db, settings.quota_budget).status()
