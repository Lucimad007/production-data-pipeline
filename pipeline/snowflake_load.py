"""Load YouTube videos into Snowflake with Snowpark."""

from __future__ import annotations

import os
from dataclasses import dataclass

from pipeline.youtube import Video

TABLE = "YOUTUBE_VIDEOS"
COLUMNS = ["VIDEO_ID", "TITLE", "CHANNEL", "PUBLISHED_AT"]

_CREATE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    VIDEO_ID VARCHAR NOT NULL,
    TITLE VARCHAR NOT NULL,
    CHANNEL VARCHAR NOT NULL,
    PUBLISHED_AT VARCHAR NOT NULL
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


def snowpark_merge(target, source) -> None:
    from snowflake.snowpark.functions import when_matched, when_not_matched

    target.merge(
        source,
        target["VIDEO_ID"] == source["VIDEO_ID"],
        [
            when_matched().update(
                {
                    "TITLE": source["TITLE"],
                    "CHANNEL": source["CHANNEL"],
                    "PUBLISHED_AT": source["PUBLISHED_AT"],
                }
            ),
            when_not_matched().insert(
                {
                    "VIDEO_ID": source["VIDEO_ID"],
                    "TITLE": source["TITLE"],
                    "CHANNEL": source["CHANNEL"],
                    "PUBLISHED_AT": source["PUBLISHED_AT"],
                }
            ),
        ],
    )


def load_videos(videos: list[Video], session, merge=snowpark_merge) -> int:
    session.sql(_CREATE).collect()
    source = session.create_dataframe(video_rows(videos), schema=COLUMNS)
    target = session.table(TABLE)
    merge(target, source)
    return int(target.count())
