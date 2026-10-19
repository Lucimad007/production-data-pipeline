"""Collect public video statistics for every upload on a YouTube channel."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from pipeline.youtube import ROOT, load_env

API_ROOT = "https://www.googleapis.com/youtube/v3"
DEFAULT_DATABASE = ROOT / "data" / "output" / "youtube.db"
DEFAULT_CHANNEL = "AlexHormozi"
BATCH_SIZE = 50

Progress = Callable[[str], None] | None

_CREATE = """
CREATE TABLE IF NOT EXISTS video_stats (
    video_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    published_at TEXT NOT NULL,
    duration TEXT NOT NULL,
    view_count INTEGER,
    like_count INTEGER,
    comment_count INTEGER
)
"""


@dataclass(frozen=True)
class Channel:
    channel_id: str
    title: str
    uploads_playlist: str


@dataclass(frozen=True)
class VideoStats:
    video_id: str
    title: str
    published_at: str
    duration: str
    view_count: int | None
    like_count: int | None
    comment_count: int | None


def _error_message(detail: str) -> str:
    try:
        return str(json.loads(detail)["error"]["message"])
    except (json.JSONDecodeError, KeyError, TypeError):
        return detail.strip() or "unknown error"


def api_get(endpoint: str, api_key: str, **params: str | int) -> dict:
    query = urllib.parse.urlencode({**params, "key": api_key})
    url = f"{API_ROOT}/{endpoint}?{query}"
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code < 500:
                raise SystemExit(
                    f"YouTube API error {error.code} on {endpoint}: {_error_message(detail)}"
                ) from error
            last_error = error
        except urllib.error.URLError as error:
            last_error = error
        if attempt < 2:
            time.sleep(2**attempt)

    raise SystemExit(f"Could not reach the YouTube API: {last_error}")


def resolve_channel(channel: str, api_key: str) -> Channel:
    identifier = channel.strip().lstrip("@")
    if not identifier:
        raise SystemExit("Pass --channel with a YouTube handle or channel id.")

    params: dict[str, str] = {"part": "snippet,contentDetails"}
    if identifier.startswith("UC") and len(identifier) == 24:
        params["id"] = identifier
    else:
        params["forHandle"] = identifier

    payload = api_get("channels", api_key, **params)
    items = payload.get("items", [])
    if not items:
        raise SystemExit(f"No YouTube channel found for {channel!r}.")

    item = items[0]
    uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
    if not uploads:
        raise SystemExit(f"Channel {channel!r} does not expose an uploads playlist.")

    return Channel(
        channel_id=item["id"],
        title=item.get("snippet", {}).get("title", ""),
        uploads_playlist=uploads,
    )


def upload_video_ids(
    playlist_id: str,
    api_key: str,
    max_videos: int = 0,
    progress: Progress = None,
) -> list[str]:
    video_ids: list[str] = []
    seen: set[str] = set()
    page_token: str | None = None
    page = 0

    while True:
        params: dict[str, str | int] = {
            "part": "contentDetails",
            "playlistId": playlist_id,
            "maxResults": BATCH_SIZE,
        }
        if page_token:
            params["pageToken"] = page_token

        payload = api_get("playlistItems", api_key, **params)
        page += 1

        for item in payload.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if not video_id or video_id in seen:
                continue
            seen.add(video_id)
            video_ids.append(video_id)
            if max_videos and len(video_ids) >= max_videos:
                if progress:
                    progress(f"uploads page={page} ids={len(video_ids)}")
                return video_ids

        if progress:
            progress(f"uploads page={page} ids={len(video_ids)}")

        page_token = payload.get("nextPageToken")
        if not page_token:
            return video_ids


def _count(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def transform_video_stats(payload: dict) -> list[VideoStats]:
    stats: list[VideoStats] = []
    for item in payload.get("items", []):
        video_id = item.get("id")
        snippet = item.get("snippet", {})
        if not video_id or not snippet.get("title"):
            continue

        statistics = item.get("statistics", {})
        stats.append(
            VideoStats(
                video_id=video_id,
                title=snippet["title"],
                published_at=snippet.get("publishedAt", ""),
                duration=item.get("contentDetails", {}).get("duration", ""),
                view_count=_count(statistics.get("viewCount")),
                like_count=_count(statistics.get("likeCount")),
                comment_count=_count(statistics.get("commentCount")),
            )
        )
    return stats


def fetch_video_stats(
    video_ids: list[str],
    api_key: str,
    progress: Progress = None,
) -> list[VideoStats]:
    stats: list[VideoStats] = []
    unique_ids = list(dict.fromkeys(video_ids))
    batches = (len(unique_ids) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch, start in enumerate(range(0, len(unique_ids), BATCH_SIZE), start=1):
        chunk = unique_ids[start : start + BATCH_SIZE]
        payload = api_get(
            "videos",
            api_key,
            part="snippet,contentDetails,statistics",
            id=",".join(chunk),
            maxResults=len(chunk),
        )
        stats.extend(transform_video_stats(payload))
        if progress:
            progress(f"statistics batch={batch}/{batches} videos={len(stats)}")

    return stats


def load_video_stats(stats: list[VideoStats], database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(_CREATE)
        connection.executemany(
            """
            INSERT INTO video_stats (
                video_id, title, published_at, duration, view_count, like_count, comment_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                published_at = excluded.published_at,
                duration = excluded.duration,
                view_count = excluded.view_count,
                like_count = excluded.like_count,
                comment_count = excluded.comment_count
            """,
            [
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
            ],
        )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM video_stats").fetchone()[0]
    return int(count)


def collect(
    channel: str,
    api_key: str,
    max_videos: int = 0,
    progress: Progress = None,
) -> tuple[Channel, list[str], list[VideoStats]]:
    resolved = resolve_channel(channel, api_key)
    if progress:
        progress(f"channel={resolved.title} id={resolved.channel_id}")
    video_ids = upload_video_ids(resolved.uploads_playlist, api_key, max_videos, progress)
    stats = fetch_video_stats(video_ids, api_key, progress)
    return resolved, video_ids, stats


def run(
    channel: str,
    database: Path,
    api_key: str,
    max_videos: int = 0,
    progress: Progress = None,
) -> tuple[Channel, int, int, int]:
    resolved, video_ids, stats = collect(channel, api_key, max_videos, progress)
    stored = load_video_stats(stats, database)
    return resolved, len(video_ids), len(stats), stored


def run_snowflake(
    channel: str,
    api_key: str,
    max_videos: int = 0,
    progress: Progress = None,
) -> tuple[Channel, int, int, int]:
    from pipeline.snowflake_load import (
        SnowflakeConfig,
        load_video_stats as load_snowflake,
        session_from_config,
    )

    resolved, video_ids, stats = collect(channel, api_key, max_videos, progress)
    session = session_from_config(SnowflakeConfig.from_env())
    try:
        stored = load_snowflake(stats, session)
    finally:
        session.close()
    return resolved, len(video_ids), len(stats), stored


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load public YouTube video statistics for a channel into SQLite or Snowflake"
    )
    parser.add_argument(
        "--channel",
        default=DEFAULT_CHANNEL,
        help="Channel handle with or without @, or a channel id (default: AlexHormozi)",
    )
    parser.add_argument(
        "--max-videos",
        type=int,
        default=0,
        help="Only collect the newest N videos (default: 0, all uploads)",
    )
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--destination", choices=("sqlite", "snowflake"), default="sqlite")
    args = parser.parse_args()

    if args.max_videos < 0:
        parser.error("--max-videos must be zero or greater")

    load_env(ROOT / ".env")
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set YOUTUBE_API_KEY to your YouTube Data API v3 key.")

    def progress(message: str) -> None:
        print(message, flush=True)

    if args.destination == "snowflake":
        channel, discovered, fetched, stored = run_snowflake(
            args.channel, api_key, args.max_videos, progress
        )
        print(f"channel={channel.title} id={channel.channel_id}")
        print(f"videos={discovered} fetched={fetched} stored={stored}")
        print("destination=snowflake table=YOUTUBE_VIDEO_STATS")
        return

    channel, discovered, fetched, stored = run(
        args.channel, args.database, api_key, args.max_videos, progress
    )
    print(f"channel={channel.title} id={channel.channel_id}")
    print(f"videos={discovered} fetched={fetched} stored={stored}")
    print(f"database={args.database}")


if __name__ == "__main__":
    main()
