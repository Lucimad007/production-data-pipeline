from __future__ import annotations

from breakout.pipeline import ingest_channel
from tests.test_breakout_storage import sample_collection


class FakeClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass

    def collect(self, channel: str, **kwargs: object):
        return sample_collection()


def test_ingest_is_idempotent(settings, monkeypatch) -> None:
    monkeypatch.setattr("breakout.pipeline.YouTubeClient", FakeClient)

    first = ingest_channel(settings, "fixture", max_videos=1)
    second = ingest_channel(settings, "fixture", max_videos=1)

    assert first.videos == 1
    assert first.snapshots == 1
    assert first.comments == 1
    assert first.quarantined == 0
    assert first.raw_files == 1
    assert first.bronze["videos"] == 1
    assert second.bronze == first.bronze
    assert second.written == first.written
