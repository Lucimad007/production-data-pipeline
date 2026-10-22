from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from breakout.contracts import (
    ApiEnvelope,
    Channel,
    ChannelSnapshot,
    Comment,
    Video,
    VideoSnapshot,
    payload_hash,
    request_hash,
)
from breakout.storage import Lakehouse, RawLanding, response_id
from breakout.youtube import Collection

NOW = datetime(2026, 10, 22, 12, 0, tzinfo=UTC)


def sample_envelope(fetched_at: datetime = NOW) -> ApiEnvelope:
    payload = {"items": [{"id": "abc"}]}
    return ApiEnvelope(
        endpoint="videos",
        params={"id": "abc", "part": "snippet"},
        fetched_at=fetched_at,
        status_code=200,
        payload=payload,
        request_hash=request_hash("videos", {"id": "abc", "part": "snippet"}),
        payload_hash=payload_hash(payload),
        units=1,
    )


def sample_collection() -> Collection:
    channel = Channel(
        channel_id="UC123",
        title="Test Channel",
        handle="@test",
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        subscriber_count=1000,
        video_count=1,
        view_count=5000,
        uploads_playlist="UU123",
    )
    video = Video(
        video_id="abc",
        channel_id="UC123",
        title="A video",
        description="desc",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        duration_iso="PT26M10S",
        duration_seconds=1570,
        tags=["test"],
        category_id="22",
        live_broadcast_content="none",
        default_language="en",
        thumbnail_url="https://example.com/thumb.jpg",
    )
    return Collection(
        channel=channel,
        channel_snapshot=ChannelSnapshot(
            channel_id="UC123",
            snapshot_at=NOW,
            title=channel.title,
            handle=channel.handle,
            subscriber_count=channel.subscriber_count,
            video_count=channel.video_count,
            view_count=channel.view_count,
            uploads_playlist=channel.uploads_playlist,
        ),
        videos=[video],
        video_snapshots=[
            VideoSnapshot(
                video_id="abc",
                channel_id="UC123",
                snapshot_at=NOW,
                view_count=100,
                like_count=10,
                comment_count=2,
            )
        ],
        comments=[
            Comment(
                comment_id="comment-1",
                video_id="abc",
                author_hash="a" * 64,
                text="Great video",
                like_count=3,
                published_at=NOW,
                updated_at=NOW,
            )
        ],
        quota_used=5,
        envelopes=[sample_envelope()],
    )


def test_raw_landing_is_idempotent_and_preserves_payload(tmp_path: Path) -> None:
    landing = RawLanding(tmp_path / "raw")
    envelope = sample_envelope()

    first = landing.write(envelope)
    second = landing.write(envelope)

    assert first == second
    assert first.exists()
    assert response_id(envelope) in first.name
    saved = json.loads(first.read_text(encoding="utf-8"))
    assert saved["endpoint"] == "videos"
    assert saved["payload"]["items"][0]["id"] == "abc"
    assert "key" not in saved["params"]


def test_lakehouse_writes_are_idempotent(settings) -> None:
    collection = sample_collection()
    with Lakehouse(settings) as lake:
        first = lake.write_collection(collection)
        second = lake.write_collection(collection)
        counts = lake.table_counts()

    assert first == {"channels": 1, "videos": 1, "video_snapshots": 1, "comments": 1}
    assert second == first
    assert counts == {
        "api_responses": 0,
        "channels": 1,
        "videos": 1,
        "video_snapshots": 1,
        "comments": 1,
    }


def test_lakehouse_upserts_video_and_snapshot(settings) -> None:
    collection = sample_collection()
    with Lakehouse(settings) as lake:
        lake.write_collection(collection)
        updated = collection.videos[0].model_copy(update={"title": "Renamed"})
        lake.write_videos([updated])
        lake.write_video_snapshots(
            [
                VideoSnapshot(
                    video_id="abc",
                    channel_id="UC123",
                    snapshot_at=NOW,
                    view_count=500,
                    like_count=50,
                    comment_count=5,
                )
            ]
        )
        video = lake.query_df("SELECT title FROM lake.bronze.videos")
        snapshot = lake.query_df("SELECT view_count FROM lake.bronze.video_snapshots")

    assert len(video) == 1
    assert video.loc[0, "title"] == "Renamed"
    assert len(snapshot) == 1
    assert int(snapshot.loc[0, "view_count"]) == 500


def test_api_responses_dedupe_by_response_id(settings) -> None:
    first = sample_envelope()
    second = sample_envelope(fetched_at=NOW + timedelta(minutes=5))
    with Lakehouse(settings) as lake:
        assert lake.write_api_responses([first, first, second]) == 2
        assert lake.write_api_responses([first]) == 0
        assert lake.table_counts()["api_responses"] == 2
