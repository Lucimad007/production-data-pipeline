"""Fetch public YouTube search results and store them in SQLite."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE = ROOT / "data" / "output" / "youtube.db"
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass(frozen=True)
class Video:
    video_id: str
    title: str
    channel: str
    published_at: str


def extract_search(query: str, api_key: str, max_results: int = 5) -> dict:
    params = urllib.parse.urlencode(
        {
            "part": "snippet",
            "type": "video",
            "q": query,
            "maxResults": max_results,
            "key": api_key,
        }
    )
    with urllib.request.urlopen(f"{SEARCH_URL}?{params}", timeout=30) as response:
        return json.load(response)


def transform_search(payload: dict) -> list[Video]:
    videos: list[Video] = []
    for item in payload.get("items", []):
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        if not video_id or not snippet.get("title"):
            continue
        videos.append(
            Video(
                video_id=video_id,
                title=snippet["title"],
                channel=snippet.get("channelTitle", ""),
                published_at=snippet.get("publishedAt", ""),
            )
        )
    return videos


def load_videos(videos: list[Video], database: Path) -> int:
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                channel TEXT NOT NULL,
                published_at TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO videos (video_id, title, channel, published_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                title = excluded.title,
                channel = excluded.channel,
                published_at = excluded.published_at
            """,
            [(video.video_id, video.title, video.channel, video.published_at) for video in videos],
        )
        connection.commit()
        count = connection.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
    return int(count)


def run(query: str, database: Path, api_key: str, max_results: int = 5) -> int:
    payload = extract_search(query, api_key, max_results)
    videos = transform_search(payload)
    return load_videos(videos, database)


def load_env(path: Path) -> None:
    """Load KEY=VALUE lines into the process environment. Existing vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    parser = argparse.ArgumentParser(description="Load YouTube search results into SQLite")
    parser.add_argument("--query", default="data pipeline")
    parser.add_argument("--max-results", type=int, default=5)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    args = parser.parse_args()

    load_env(ROOT / ".env")
    api_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set YOUTUBE_API_KEY to your YouTube Data API v3 key.")

    stored = run(args.query, args.database, api_key, args.max_results)
    print(f"query={args.query} stored={stored}")
    print(f"database={args.database}")


if __name__ == "__main__":
    main()
