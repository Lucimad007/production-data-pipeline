"""Load YouTube videos into Snowflake with Snowpark."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pipeline.video_stats import VideoStats
from pipeline.youtube import Video

TABLE = "YOUTUBE_VIDEOS"
COLUMNS = ["VIDEO_ID", "TITLE", "CHANNEL", "PUBLISHED_AT"]

VIDEO_STATS_TABLE = "YOUTUBE_VIDEO_STATS"
VIDEO_STATS_COLUMNS = [
    "VIDEO_ID",
    "TITLE",
    "PUBLISHED_AT",
    "DURATION",
    "VIEW_COUNT",
    "LIKE_COUNT",
    "COMMENT_COUNT",
]

_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    VIDEO_ID VARCHAR NOT NULL,
    TITLE VARCHAR NOT NULL,
    CHANNEL VARCHAR NOT NULL,
    PUBLISHED_AT VARCHAR NOT NULL
)
"""

_CREATE_VIDEO_STATS = f"""
CREATE TABLE IF NOT EXISTS {VIDEO_STATS_TABLE} (
    VIDEO_ID VARCHAR NOT NULL,
    TITLE VARCHAR NOT NULL,
    PUBLISHED_AT VARCHAR NOT NULL,
    DURATION VARCHAR NOT NULL,
    VIEW_COUNT NUMBER,
    LIKE_COUNT NUMBER,
    COMMENT_COUNT NUMBER
)
"""


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str

    @classmethod
    def from_env(cls) -> "SnowflakeConfig":
        values = {
            "account": os.environ.get("SNOWFLAKE_ACCOUNT", "").strip(),
            "user": os.environ.get("SNOWFLAKE_USER", "").strip(),
            "password": os.environ.get("SNOWFLAKE_PASSWORD", "").strip(),
            "warehouse": os.environ.get("SNOWFLAKE_WAREHOUSE", "").strip(),
            "database": os.environ.get("SNOWFLAKE_DATABASE", "").strip(),
            "schema": os.environ.get("SNOWFLAKE_SCHEMA", "").strip(),
            "role": os.environ.get("SNOWFLAKE_ROLE", "").strip(),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            names = ", ".join(f"SNOWFLAKE_{name.upper()}" for name in missing)
            raise SystemExit(f"Set {names} in .env before loading to Snowflake.")
        return cls(**values)

    def as_session_config(self) -> dict[str, str]:
        return {
            "account": self.account,
            "user": self.user,
            "password": self.password,
            "warehouse": self.warehouse,
            "database": self.database,
            "schema": self.schema,
            "role": self.role,
        }


def video_rows(videos: list[Video]) -> list[tuple[str, str, str, str]]:
    return [(video.video_id, video.title, video.channel, video.published_at) for video in videos]


def session_from_config(config: SnowflakeConfig):
    from snowflake.snowpark import Session

    return Session.builder.configs(config.as_session_config()).create()


def snowpark_merge_rows(target, source, columns: list[str], key: str = "VIDEO_ID") -> None:
    from snowflake.snowpark.functions import when_matched, when_not_matched

    target.merge(
        target[key] == source[key],
        [
            when_matched().update(
                {column: source[column] for column in columns if column != key}
            ),
            when_not_matched().insert({column: source[column] for column in columns}),
        ],
    )


def snowpark_merge(target, source) -> None:
    snowpark_merge_rows(target, source, COLUMNS)


def snowpark_video_stats_merge(target, source) -> None:
    snowpark_merge_rows(target, source, VIDEO_STATS_COLUMNS)


def load_videos(videos: list[Video], session, merge=snowpark_merge) -> int:
    session.sql(_CREATE).collect()
    source = session.create_dataframe(video_rows(videos), schema=COLUMNS)
    target = session.table(TABLE)
    merge(target, source)
    return int(target.count())


def video_stat_rows(
    stats: list[VideoStats],
) -> list[tuple[str, str, str, str, int | None, int | None, int | None]]:
    return [
        (
            video.video_id,
            video.title,
            video.published_at,
            video.duration,
            video.view_count,
            video.like_count,
            video.comment_count,
        )
        for video in stats
    ]


def load_video_stats(stats: list[VideoStats], session, merge=snowpark_video_stats_merge) -> int:
    session.sql(_CREATE_VIDEO_STATS).collect()
    source = session.create_dataframe(video_stat_rows(stats), schema=VIDEO_STATS_COLUMNS)
    target = session.table(VIDEO_STATS_TABLE)
    merge(target, source)
    return int(target.count())
