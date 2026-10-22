import sqlite3
import unittest
from pathlib import Path
from unittest.mock import patch

from pipeline.video_stats import (
    VideoStats,
    fetch_video_stats,
    load_video_stats,
    resolve_channel,
    transform_video_stats,
    upload_video_ids,
)

ROOT = Path(__file__).resolve().parents[1]


def sample_stats(**overrides) -> VideoStats:
    values = {
        "video_id": "abc",
        "title": "Sample",
        "published_at": "2026-01-01T00:00:00Z",
        "duration": "PT26M10S",
        "view_count": 100,
        "like_count": 10,
        "comment_count": 2,
    }
    values.update(overrides)
    return VideoStats(**values)


class VideoStatsTransformTest(unittest.TestCase):
    def test_keeps_video_statistics(self) -> None:
        payload = {
            "items": [
                {
                    "id": "abc",
                    "snippet": {
                        "title": "$10,000 Every Day",
                        "publishedAt": "2024-06-01T16:00:00Z",
                    },
                    "contentDetails": {"duration": "PT26M10S"},
                    "statistics": {
                        "viewCount": "174883772",
                        "likeCount": "7093805",
                        "commentCount": "347371",
                    },
                },
                {
                    "id": "def",
                    "snippet": {
                        "title": "No likes",
                        "publishedAt": "2024-06-02T16:00:00Z",
                    },
                    "contentDetails": {"duration": "PT1M"},
                    "statistics": {"viewCount": "5"},
                },
                {"snippet": {"title": "Missing id"}},
            ]
        }

        stats = transform_video_stats(payload)

        self.assertEqual(
            stats,
            [
                VideoStats(
                    "abc",
                    "$10,000 Every Day",
                    "2024-06-01T16:00:00Z",
                    "PT26M10S",
                    174883772,
                    7093805,
                    347371,
                ),
                VideoStats(
                    "def",
                    "No likes",
                    "2024-06-02T16:00:00Z",
                    "PT1M",
                    5,
                    None,
                    None,
                ),
            ],
        )

    def test_load_upserts_statistics(self) -> None:
        database = ROOT / "data" / "output" / "test_video_stats.db"
        if database.exists():
            database.unlink()

        self.assertEqual(load_video_stats([sample_stats()], database), 1)
        self.assertEqual(
            load_video_stats([sample_stats(title="Renamed", view_count=250)], database),
            1,
        )

        with sqlite3.connect(database) as connection:
            row = connection.execute(
                "SELECT title, view_count, like_count, comment_count FROM video_stats"
            ).fetchone()
        self.assertEqual(row, ("Renamed", 250, 10, 2))


class VideoStatsApiTest(unittest.TestCase):
    def test_upload_ids_follows_pages(self) -> None:
        pages = {
            None: {
                "items": [
                    {"contentDetails": {"videoId": "a"}},
                    {"contentDetails": {"videoId": "b"}},
                ],
                "nextPageToken": "next",
            },
            "next": {
                "items": [
                    {"contentDetails": {"videoId": "b"}},
                    {"contentDetails": {"videoId": "c"}},
                ]
            },
        }

        def fake_api(endpoint: str, api_key: str, **params):
            self.assertEqual(endpoint, "playlistItems")
            self.assertEqual(params["playlistId"], "uploads")
            return pages[params.get("pageToken")]

        with patch("pipeline.video_stats.api_get", side_effect=fake_api):
            video_ids = upload_video_ids("uploads", "key")

        self.assertEqual(video_ids, ["a", "b", "c"])

    def test_upload_ids_stops_at_max_videos(self) -> None:
        payload = {"items": [{"contentDetails": {"videoId": name}} for name in "abc"]}

        with patch("pipeline.video_stats.api_get", return_value=payload):
            video_ids = upload_video_ids("uploads", "key", max_videos=2)

        self.assertEqual(video_ids, ["a", "b"])

    def test_fetch_video_stats_batches_ids(self) -> None:
        video_ids = [str(index) for index in range(51)]
        calls: list[str] = []

        def fake_api(endpoint: str, api_key: str, **params):
            self.assertEqual(endpoint, "videos")
            calls.append(params["id"])
            items = [
                {
                    "id": video_id,
                    "snippet": {"title": f"Video {video_id}", "publishedAt": "2026-01-01"},
                    "contentDetails": {"duration": "PT1M"},
                    "statistics": {"viewCount": "1"},
                }
                for video_id in params["id"].split(",")
            ]
            return {"items": items}

        with patch("pipeline.video_stats.api_get", side_effect=fake_api):
            stats = fetch_video_stats(video_ids, "key")

        self.assertEqual(len(calls), 2)
        self.assertEqual(len(calls[0].split(",")), 50)
        self.assertEqual(len(calls[1].split(",")), 1)
        self.assertEqual(len(stats), 51)

    def test_resolve_channel_uses_handle(self) -> None:
        payload = {
            "items": [
                {
                    "id": "UC123",
                    "snippet": {"title": "Alex Hormozi"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
                }
            ]
        }

        def fake_api(endpoint: str, api_key: str, **params):
            self.assertEqual(endpoint, "channels")
            self.assertEqual(params["forHandle"], "AlexHormozi")
            return payload

        with patch("pipeline.video_stats.api_get", side_effect=fake_api):
            channel = resolve_channel("@AlexHormozi", "key")

        self.assertEqual(channel.channel_id, "UC123")
        self.assertEqual(channel.title, "Alex Hormozi")
        self.assertEqual(channel.uploads_playlist, "UU123")


if __name__ == "__main__":
    unittest.main()
