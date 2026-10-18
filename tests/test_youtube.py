import sqlite3
import unittest
from pathlib import Path

from pipeline.youtube import load_videos, transform_search, Video

ROOT = Path(__file__).resolve().parents[1]


class YoutubeTransformTest(unittest.TestCase):
    def test_keeps_videos_with_ids(self) -> None:
        payload = {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "abc"},
                    "snippet": {
                        "title": "Sample",
                        "channelTitle": "Channel",
                        "publishedAt": "2026-01-01T00:00:00Z",
                    },
                },
                {"id": {"kind": "youtube#channel"}, "snippet": {"title": "Skip"}},
            ]
        }
        videos = transform_search(payload)
        self.assertEqual(videos, [Video("abc", "Sample", "Channel", "2026-01-01T00:00:00Z")])

    def test_load_upserts(self) -> None:
        database = ROOT / "data" / "output" / "test_youtube.db"
        if database.exists():
            database.unlink()
        video = Video("abc", "Sample", "Channel", "2026-01-01T00:00:00Z")
        self.assertEqual(load_videos([video], database), 1)
        self.assertEqual(load_videos([Video("abc", "Renamed", "Channel", "2026-01-02T00:00:00Z")], database), 1)
        with sqlite3.connect(database) as connection:
            title = connection.execute("SELECT title FROM videos").fetchone()[0]
        self.assertEqual(title, "Renamed")


if __name__ == "__main__":
    unittest.main()
