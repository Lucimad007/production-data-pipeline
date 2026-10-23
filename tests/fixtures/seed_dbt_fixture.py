"""Seed a deterministic DuckLake fixture for dbt CI.

This is synthetic data. It exists so `dbt build` can run in CI without API
credentials or a live channel. It is never mixed into the real demo marts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from breakout.config import Settings
from breakout.contracts import (
    Channel,
    ChannelSnapshot,
    Comment,
    Video,
    VideoSnapshot,
)
from breakout.storage import Lakehouse
from breakout.youtube import Collection

ROOT = Path(".tmp/dbt")
SNAPSHOT_AT = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)


def build_collection() -> Collection:
    channel_id = "UC_FIXTURE"
    topics = [
        ("money", "How to make money part {index}"),
        ("sales", "Sales closing secrets {index}"),
        ("fitness", "Fitness workout plan {index}"),
    ]
    age_weeks = [1, 2, 4, 8, 16, 32]
    publish_hours = [10, 14, 18]
    base_views = {1: 2_000, 2: 4_000, 4: 9_000, 8: 18_000, 16: 30_000, 32: 45_000}

    videos: list[Video] = []
    snapshots: list[VideoSnapshot] = []
    for index in range(30):
        topic, title_template = topics[index % len(topics)]
        weeks = age_weeks[index % len(age_weeks)]
        published_at = (SNAPSHOT_AT - timedelta(weeks=weeks)).replace(
            hour=publish_hours[index % len(publish_hours)]
        )
        video_id = f"fixture-{index:02d}"
        title = title_template.format(index=index)
        topic_factor = {"money": 1.3, "sales": 1.0, "fitness": 0.8}[topic]
        views = int(base_views[weeks] * topic_factor * (1 + (index % 5) * 0.18))
        videos.append(
            Video(
                video_id=video_id,
                channel_id=channel_id,
                title=title,
                description=f"{topic} fixture video",
                published_at=published_at,
                duration_iso="PT10M",
                duration_seconds=600,
                tags=[topic],
                category_id="22",
                live_broadcast_content="none",
                default_language="en",
                thumbnail_url=None,
            )
        )
        snapshots.append(
            VideoSnapshot(
                video_id=video_id,
                channel_id=channel_id,
                snapshot_at=SNAPSHOT_AT,
                view_count=views,
                like_count=int(views * 0.03),
                comment_count=int(views * 0.005),
            )
        )

    comments = [
        Comment(
            comment_id=f"fixture-comment-{index}",
            video_id=f"fixture-{index:02d}",
            author_hash=f"{index:064d}",
            text="Synthetic fixture comment",
            like_count=index,
            published_at=SNAPSHOT_AT - timedelta(days=1),
            updated_at=SNAPSHOT_AT - timedelta(days=1),
        )
        for index in range(10)
    ]

    channel = Channel(
        channel_id=channel_id,
        title="Fixture Channel",
        handle="@fixture",
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        subscriber_count=10_000,
        video_count=len(videos),
        view_count=sum(item.view_count or 0 for item in snapshots),
        uploads_playlist="UU_FIXTURE",
    )
    return Collection(
        channel=channel,
        channel_snapshot=ChannelSnapshot(
            channel_id=channel_id,
            snapshot_at=SNAPSHOT_AT,
            title=channel.title,
            handle=channel.handle,
            subscriber_count=channel.subscriber_count,
            video_count=channel.video_count,
            view_count=channel.view_count,
            uploads_playlist=channel.uploads_playlist,
        ),
        videos=videos,
        video_snapshots=snapshots,
        comments=comments,
        quota_used=0,
    )


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    settings = Settings(
        _env_file=None,
        youtube_api_key="fixture",
        data_dir=ROOT,
        raw_dir=ROOT / "raw",
        duckdb_path=ROOT / "breakout.duckdb",
        ducklake_catalog=ROOT / "catalog.sqlite",
        ducklake_data=ROOT / "lake",
        quota_db=ROOT / "quota.sqlite",
    )
    with Lakehouse(settings) as lake:
        lake.write_collection(build_collection())
        print("fixture=" + " ".join(f"{k}:{v}" for k, v in lake.table_counts().items()))


if __name__ == "__main__":
    main()
