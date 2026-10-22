from __future__ import annotations

from datetime import UTC, datetime

import pytest

from breakout.contracts import (
    Channel,
    Comment,
    Video,
    parse_datetime,
    parse_duration_seconds,
    parse_int,
    request_hash,
)


def test_parse_duration_seconds() -> None:
    assert parse_duration_seconds("PT26M10S") == 1570
    assert parse_duration_seconds("PT1H2M3S") == 3723
    assert parse_duration_seconds("P1DT1S") == 86401
    assert parse_duration_seconds("PT0S") == 0
    assert parse_duration_seconds("P0D") == 0
    assert parse_duration_seconds(None) is None
    assert parse_duration_seconds("not-a-duration") is None


def test_parse_int_handles_hidden_counts() -> None:
    assert parse_int("123") == 123
    assert parse_int(123) == 123
    assert parse_int(None) is None
    assert parse_int("") is None
    assert parse_int("hidden") is None


def test_parse_datetime_is_timezone_aware() -> None:
    parsed = parse_datetime("2026-10-22T17:05:20Z")
    assert parsed == datetime(2026, 10, 22, 17, 5, 20, tzinfo=UTC)
    assert parsed is not None
    assert parsed.tzinfo is not None


def test_request_hash_excludes_api_key() -> None:
    first = request_hash("videos", {"id": "abc", "part": "snippet", "key": "secret"})
    second = request_hash("videos", {"id": "abc", "part": "snippet"})
    assert first == second
    assert request_hash("videos", {"id": "abc"}) != request_hash("videos", {"id": "def"})


def test_channel_contract() -> None:
    channel = Channel.from_api(
        {
            "id": "UC123",
            "snippet": {"title": "Channel", "customUrl": "@channel", "publishedAt": "2020-01-01T00:00:00Z"},
            "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
            "statistics": {"subscriberCount": "100", "videoCount": "5", "viewCount": "1000"},
        }
    )
    assert channel.channel_id == "UC123"
    assert channel.uploads_playlist == "UU123"
    assert channel.subscriber_count == 100


def test_channel_contract_rejects_missing_uploads() -> None:
    with pytest.raises(ValueError):
        Channel.from_api({"id": "UC123", "snippet": {"title": "Channel"}})


def test_video_contract() -> None:
    video = Video.from_api(
        {
            "id": "abc",
            "snippet": {
                "channelId": "UC123",
                "title": "A video",
                "description": "desc",
                "publishedAt": "2026-01-01T00:00:00Z",
                "tags": ["a", "b"],
                "thumbnails": {"high": {"url": "https://example.com/thumb.jpg"}},
            },
            "contentDetails": {"duration": "PT26M10S"},
            "statistics": {"viewCount": "100"},
        }
    )
    assert video.video_id == "abc"
    assert video.duration_seconds == 1570
    assert video.tags == ["a", "b"]
    assert video.thumbnail_url == "https://example.com/thumb.jpg"


def test_comment_contract_hashes_author() -> None:
    comment = Comment.from_thread(
        {
            "snippet": {
                "topLevelComment": {
                    "id": "comment-1",
                    "snippet": {
                        "authorDisplayName": "Someone",
                        "authorChannelId": {"value": "UCABC"},
                        "textDisplay": "Great video",
                        "likeCount": 3,
                        "publishedAt": "2026-01-01T00:00:00Z",
                    },
                }
            }
        },
        video_id="abc",
    )
    assert comment is not None
    assert comment.comment_id == "comment-1"
    assert comment.author_hash != "UCABC"
    assert len(comment.author_hash) == 64
    assert comment.text == "Great video"
