import os
import unittest

from pipeline.snowflake_load import (
    COLUMNS,
    VIDEO_STATS_COLUMNS,
    VIDEO_STATS_TABLE,
    SnowflakeConfig,
    load_video_stats,
    load_videos,
    video_rows,
    video_stat_rows,
)
from pipeline.video_stats import VideoStats
from pipeline.youtube import Video


class FakeFrame:
    def __init__(self, rows=None) -> None:
        self.rows = rows

    def count(self) -> int:
        return 1


class FakeSession:
    def __init__(self) -> None:
        self.created = None
        self.table_name = None
        self.statements: list[str] = []

    def sql(self, statement: str):
        self.statements.append(statement)
        return self

    def collect(self) -> None:
        return None

    def create_dataframe(self, rows, schema):
        self.created = (rows, schema)
        return FakeFrame(rows)

    def table(self, name: str) -> FakeFrame:
        self.table_name = name
        return FakeFrame()


class SnowflakeLoadTest(unittest.TestCase):
    def test_from_env_requires_every_setting(self) -> None:
        saved = {name: value for name, value in os.environ.items() if name.startswith("SNOWFLAKE_")}
        for name in list(saved):
            del os.environ[name]
        try:
            with self.assertRaises(SystemExit):
                SnowflakeConfig.from_env()
        finally:
            os.environ.update(saved)

    def test_rows_keep_video_fields(self) -> None:
        video = Video("abc", "Title", "Channel", "2026-01-01T00:00:00Z")
        self.assertEqual(video_rows([video]), [("abc", "Title", "Channel", "2026-01-01T00:00:00Z")])

    def test_load_creates_dataframe_and_merges(self) -> None:
        session = FakeSession()
        merged: list[tuple] = []
        videos = [Video("abc", "Title", "Channel", "2026-01-01T00:00:00Z")]

        stored = load_videos(videos, session, merge=lambda target, source: merged.append((target, source)))

        self.assertEqual(stored, 1)
        self.assertIn("CREATE TABLE IF NOT EXISTS YOUTUBE_VIDEOS", session.statements[0])
        self.assertEqual(session.created, (video_rows(videos), COLUMNS))
        self.assertEqual(session.table_name, "YOUTUBE_VIDEOS")
        self.assertEqual(len(merged), 1)

    def test_stat_rows_keep_video_fields(self) -> None:
        stats = [
            VideoStats(
                "abc",
                "Title",
                "2026-01-01T00:00:00Z",
                "PT26M10S",
                100,
                10,
                2,
            )
        ]
        self.assertEqual(
            video_stat_rows(stats),
            [("abc", "Title", "2026-01-01T00:00:00Z", "PT26M10S", 100, 10, 2)],
        )

    def test_load_video_stats_creates_dataframe_and_merges(self) -> None:
        session = FakeSession()
        merged: list[tuple] = []
        stats = [
            VideoStats(
                "abc",
                "Title",
                "2026-01-01T00:00:00Z",
                "PT26M10S",
                100,
                10,
                2,
            )
        ]

        stored = load_video_stats(
            stats, session, merge=lambda target, source: merged.append((target, source))
        )

        self.assertEqual(stored, 1)
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS YOUTUBE_VIDEO_STATS", session.statements[0]
        )
        self.assertEqual(session.created, (video_stat_rows(stats), VIDEO_STATS_COLUMNS))
        self.assertEqual(session.table_name, VIDEO_STATS_TABLE)
        self.assertEqual(len(merged), 1)


if __name__ == "__main__":
    unittest.main()
