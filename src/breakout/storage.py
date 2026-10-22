"""Raw landing and the DuckLake bronze layer.

Design rules:
- Raw API responses are immutable and written before any parsing.
- Bronze writes are idempotent on natural keys.
- DuckLake does not enforce primary keys, so uniqueness is enforced here and
  verified by dbt tests downstream.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import structlog

from breakout.config import Settings, get_settings
from breakout.contracts import (
    ApiEnvelope,
    ChannelSnapshot,
    Comment,
    Video,
    VideoSnapshot,
    sha256_text,
    utc_now,
)
from breakout.youtube import Collection, QuarantinedItem

log = structlog.get_logger(__name__)

BRONZE_TABLES = (
    "api_responses",
    "channels",
    "videos",
    "video_snapshots",
    "comments",
    "quarantine",
)


def _naive_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.astimezone(UTC).replace(tzinfo=None)


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def response_id(envelope: ApiEnvelope) -> str:
    return sha256_text(
        f"{envelope.request_hash}|{envelope.fetched_at.isoformat()}|{envelope.payload_hash}"
    )


class RawLanding:
    """Immutable JSON landing zone, partitioned by endpoint and date."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, envelope: ApiEnvelope) -> Path:
        day = envelope.fetched_at.astimezone(UTC).date().isoformat()
        return self.root / f"endpoint={envelope.endpoint}" / f"dt={day}" / f"{response_id(envelope)}.json"

    def write(self, envelope: ApiEnvelope) -> Path:
        path = self.path_for(envelope)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(envelope.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(path)
        return path


class Lakehouse:
    """DuckDB + DuckLake connection and bronze writer."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.settings.ensure_dirs()
        self._con = duckdb.connect(str(self.settings.duckdb_path))
        self._con.execute("INSTALL ducklake; LOAD ducklake;")
        self._attach()
        self._ensure_schema()

    def _attach(self) -> None:
        catalog = _sql_path(self.settings.ducklake_catalog)
        data = _sql_path(self.settings.ducklake_data)
        self._con.execute(
            f"ATTACH IF NOT EXISTS 'ducklake:sqlite:{catalog}' AS lake (DATA_PATH '{data}')"
        )

    def _ensure_schema(self) -> None:
        self._con.execute("CREATE SCHEMA IF NOT EXISTS lake.bronze")
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.api_responses (
                response_id VARCHAR,
                request_hash VARCHAR,
                endpoint VARCHAR,
                params_json VARCHAR,
                fetched_at TIMESTAMP,
                status_code INTEGER,
                payload_json VARCHAR,
                payload_hash VARCHAR,
                units INTEGER
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.channels (
                channel_id VARCHAR,
                snapshot_at TIMESTAMP,
                title VARCHAR,
                handle VARCHAR,
                subscriber_count BIGINT,
                video_count BIGINT,
                view_count BIGINT,
                uploads_playlist VARCHAR,
                ingested_at TIMESTAMP
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.videos (
                video_id VARCHAR,
                channel_id VARCHAR,
                title VARCHAR,
                description VARCHAR,
                published_at TIMESTAMP,
                duration_iso VARCHAR,
                duration_seconds INTEGER,
                tags_json VARCHAR,
                category_id VARCHAR,
                live_broadcast_content VARCHAR,
                default_language VARCHAR,
                thumbnail_url VARCHAR,
                ingested_at TIMESTAMP
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.video_snapshots (
                video_id VARCHAR,
                channel_id VARCHAR,
                snapshot_at TIMESTAMP,
                view_count BIGINT,
                like_count BIGINT,
                comment_count BIGINT,
                ingested_at TIMESTAMP
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.comments (
                comment_id VARCHAR,
                video_id VARCHAR,
                author_hash VARCHAR,
                text VARCHAR,
                like_count BIGINT,
                published_at TIMESTAMP,
                updated_at TIMESTAMP,
                parent_id VARCHAR,
                ingested_at TIMESTAMP
            )
            """
        )
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS lake.bronze.quarantine (
                endpoint VARCHAR,
                item_index INTEGER,
                item_id VARCHAR,
                reason VARCHAR,
                payload_hash VARCHAR,
                ingested_at TIMESTAMP
            )
            """
        )

    @property
    def connection(self) -> duckdb.DuckDBPyConnection:
        return self._con

    def close(self) -> None:
        self._con.close()

    def __enter__(self) -> Lakehouse:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def execute(self, sql: str, params: list[Any] | None = None) -> None:
        self._con.execute(sql, params or [])

    def query_df(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        return self._con.execute(sql, params or []).df()

    def table_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for table in BRONZE_TABLES:
            row = self._con.execute(f"SELECT COUNT(*) FROM lake.bronze.{table}").fetchone()
            counts[table] = int(row[0]) if row else 0
        return counts

    def write_api_response(self, envelope: ApiEnvelope) -> int:
        frame = pd.DataFrame(
            [
                {
                    "response_id": response_id(envelope),
                    "request_hash": envelope.request_hash,
                    "endpoint": envelope.endpoint,
                    "params_json": json.dumps(envelope.params, sort_keys=True),
                    "fetched_at": _naive_utc(envelope.fetched_at),
                    "status_code": envelope.status_code,
                    "payload_json": json.dumps(envelope.payload, ensure_ascii=False),
                    "payload_hash": envelope.payload_hash,
                    "units": envelope.units,
                }
            ]
        )
        return self._insert_missing(
            "api_responses", frame, key_columns=["response_id"]
        )

    def write_api_responses(self, envelopes: list[ApiEnvelope]) -> int:
        if not envelopes:
            return 0
        rows = [
            {
                "response_id": response_id(envelope),
                "request_hash": envelope.request_hash,
                "endpoint": envelope.endpoint,
                "params_json": json.dumps(envelope.params, sort_keys=True),
                "fetched_at": _naive_utc(envelope.fetched_at),
                "status_code": envelope.status_code,
                "payload_json": json.dumps(envelope.payload, ensure_ascii=False),
                "payload_hash": envelope.payload_hash,
                "units": envelope.units,
            }
            for envelope in envelopes
        ]
        return self._insert_missing(
            "api_responses", pd.DataFrame(rows), key_columns=["response_id"]
        )

    def write_channel_snapshot(self, snapshot: ChannelSnapshot) -> int:
        frame = pd.DataFrame(
            [
                {
                    "channel_id": snapshot.channel_id,
                    "snapshot_at": _naive_utc(snapshot.snapshot_at),
                    "title": snapshot.title,
                    "handle": snapshot.handle,
                    "subscriber_count": snapshot.subscriber_count,
                    "video_count": snapshot.video_count,
                    "view_count": snapshot.view_count,
                    "uploads_playlist": snapshot.uploads_playlist,
                    "ingested_at": _naive_utc(utc_now()),
                }
            ]
        )
        return self._upsert("channels", frame, key_columns=["channel_id", "snapshot_at"])

    def write_videos(self, videos: list[Video]) -> int:
        if not videos:
            return 0
        ingested_at = _naive_utc(utc_now())
        frame = pd.DataFrame(
            [
                {
                    "video_id": video.video_id,
                    "channel_id": video.channel_id,
                    "title": video.title,
                    "description": video.description,
                    "published_at": _naive_utc(video.published_at),
                    "duration_iso": video.duration_iso,
                    "duration_seconds": video.duration_seconds,
                    "tags_json": json.dumps(video.tags, ensure_ascii=False),
                    "category_id": video.category_id,
                    "live_broadcast_content": video.live_broadcast_content,
                    "default_language": video.default_language,
                    "thumbnail_url": video.thumbnail_url,
                    "ingested_at": ingested_at,
                }
                for video in videos
            ]
        )
        return self._upsert("videos", frame, key_columns=["video_id"])

    def write_video_snapshots(self, snapshots: list[VideoSnapshot]) -> int:
        if not snapshots:
            return 0
        ingested_at = _naive_utc(utc_now())
        frame = pd.DataFrame(
            [
                {
                    "video_id": snapshot.video_id,
                    "channel_id": snapshot.channel_id,
                    "snapshot_at": _naive_utc(snapshot.snapshot_at),
                    "view_count": snapshot.view_count,
                    "like_count": snapshot.like_count,
                    "comment_count": snapshot.comment_count,
                    "ingested_at": ingested_at,
                }
                for snapshot in snapshots
            ]
        )
        return self._upsert(
            "video_snapshots", frame, key_columns=["video_id", "snapshot_at"]
        )

    def write_comments(self, comments: list[Comment]) -> int:
        if not comments:
            return 0
        ingested_at = _naive_utc(utc_now())
        frame = pd.DataFrame(
            [
                {
                    "comment_id": comment.comment_id,
                    "video_id": comment.video_id,
                    "author_hash": comment.author_hash,
                    "text": comment.text,
                    "like_count": comment.like_count,
                    "published_at": _naive_utc(comment.published_at),
                    "updated_at": _naive_utc(comment.updated_at),
                    "parent_id": comment.parent_id,
                    "ingested_at": ingested_at,
                }
                for comment in comments
            ]
        )
        return self._upsert("comments", frame, key_columns=["comment_id"])

    def write_quarantine(self, records: list[QuarantinedItem]) -> int:
        if not records:
            return 0
        ingested_at = _naive_utc(utc_now())
        frame = pd.DataFrame(
            [
                {
                    "endpoint": record.endpoint,
                    "item_index": record.item_index,
                    "item_id": record.item_id,
                    "reason": record.reason,
                    "payload_hash": record.payload_hash,
                    "ingested_at": ingested_at,
                }
                for record in records
            ]
        )
        return self._upsert(
            "quarantine", frame, key_columns=["payload_hash", "item_index"]
        )

    def write_collection(self, collection: Collection) -> dict[str, int]:
        return {
            "channels": self.write_channel_snapshot(collection.channel_snapshot),
            "videos": self.write_videos(collection.videos),
            "video_snapshots": self.write_video_snapshots(collection.video_snapshots),
            "comments": self.write_comments(collection.comments),
            "quarantine": self.write_quarantine(collection.quarantined),
        }

    # -- internals ---------------------------------------------------------

    def _upsert(self, table: str, frame: pd.DataFrame, key_columns: list[str]) -> int:
        if frame.empty:
            return 0
        frame = frame.drop_duplicates(subset=key_columns, keep="first")
        columns = list(frame.columns)
        column_list = ", ".join(columns)
        key_predicate = " AND ".join(f"i.{key} = t.{key}" for key in key_columns)
        self._con.register("_incoming", frame)
        try:
            self._con.execute(
                f"""
                DELETE FROM lake.bronze.{table} AS t
                WHERE EXISTS (SELECT 1 FROM _incoming AS i WHERE {key_predicate})
                """
            )
            self._con.execute(
                f"""
                INSERT INTO lake.bronze.{table} ({column_list})
                SELECT {column_list} FROM _incoming
                """
            )
            count = len(frame)
        finally:
            self._con.unregister("_incoming")
        log.info("bronze.write", table=table, rows=count)
        return count

    def _insert_missing(
        self, table: str, frame: pd.DataFrame, key_columns: list[str]
    ) -> int:
        if frame.empty:
            return 0
        frame = frame.drop_duplicates(subset=key_columns, keep="first")
        columns = list(frame.columns)
        column_list = ", ".join(columns)
        predicate = " AND ".join(f"i.{key} = t.{key}" for key in key_columns)
        self._con.register("_incoming", frame)
        try:
            before = int(
                self._con.execute(
                    f"SELECT COUNT(*) FROM lake.bronze.{table}"
                ).fetchall()[0][0]
            )
            self._con.execute(
                f"""
                INSERT INTO lake.bronze.{table} ({column_list})
                SELECT {column_list} FROM _incoming AS i
                WHERE NOT EXISTS (
                    SELECT 1 FROM lake.bronze.{table} AS t WHERE {predicate}
                )
                """
            )
            after = int(
                self._con.execute(
                    f"SELECT COUNT(*) FROM lake.bronze.{table}"
                ).fetchall()[0][0]
            )
        finally:
            self._con.unregister("_incoming")
        inserted = int(after) - int(before)
        log.info("bronze.insert_missing", table=table, rows=inserted)
        return inserted


def utc_date() -> str:
    return datetime.now(UTC).date().isoformat()
