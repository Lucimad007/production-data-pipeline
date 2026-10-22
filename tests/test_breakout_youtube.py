from __future__ import annotations

import httpx
import pytest
import respx

from breakout.config import Settings
from breakout.youtube import QuotaExceeded, QuotaLedger, YouTubeClient, YouTubeError

CHANNELS_URL = "https://www.googleapis.com/youtube/v3/channels"
PLAYLIST_URL = "https://www.googleapis.com/youtube/v3/playlistItems"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
COMMENTS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"


def channel_payload() -> dict:
    return {
        "items": [
            {
                "id": "UC123",
                "snippet": {
                    "title": "Test Channel",
                    "customUrl": "@test",
                    "publishedAt": "2020-01-01T00:00:00Z",
                },
                "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
                "statistics": {
                    "subscriberCount": "1000",
                    "videoCount": "2",
                    "viewCount": "5000",
                },
            }
        ]
    }


def video_item(video_id: str) -> dict:
    return {
        "id": video_id,
        "snippet": {
            "channelId": "UC123",
            "title": f"Video {video_id}",
            "description": "desc",
            "publishedAt": "2026-01-01T00:00:00Z",
            "tags": ["test"],
        },
        "contentDetails": {"duration": "PT1M"},
        "statistics": {"viewCount": "10", "likeCount": "2", "commentCount": "1"},
    }


def make_client(settings: Settings, sleeps: list[float] | None = None) -> YouTubeClient:
    ledger = QuotaLedger(settings.quota_db, settings.quota_budget)
    return YouTubeClient(
        "test-key",
        settings=settings,
        http_client=httpx.Client(),
        ledger=ledger,
        sleep=(sleeps.append if sleeps is not None else (lambda _: None)),
    )


@respx.mock
def test_resolve_channel_parses_and_records_quota(settings: Settings) -> None:
    route = respx.get(CHANNELS_URL).mock(
        return_value=httpx.Response(200, json=channel_payload())
    )
    client = make_client(settings)

    channel = client.resolve_channel("@test")

    assert channel.channel_id == "UC123"
    assert channel.uploads_playlist == "UU123"
    assert route.call_count == 1
    assert route.calls[0].request.url.params["forHandle"] == "test"
    assert client.ledger.used_today() == 1
    assert len(client.envelopes) == 1


@respx.mock
def test_retries_server_errors_then_records_once(settings: Settings) -> None:
    sleeps: list[float] = []
    route = respx.get(CHANNELS_URL).mock(
        side_effect=[
            httpx.Response(500, json={"error": {"message": "boom"}}),
            httpx.Response(200, json=channel_payload()),
        ]
    )
    client = make_client(settings, sleeps)

    channel = client.resolve_channel("test")

    assert channel.channel_id == "UC123"
    assert route.call_count == 2
    assert client.ledger.used_today() == 1
    assert any(value > 0 for value in sleeps)


@respx.mock
def test_respects_retry_after(settings: Settings) -> None:
    sleeps: list[float] = []
    respx.get(CHANNELS_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "7"}),
            httpx.Response(200, json=channel_payload()),
        ]
    )
    client = make_client(settings, sleeps)

    client.resolve_channel("test")

    assert 7.0 in sleeps


@respx.mock
def test_does_not_retry_client_errors(settings: Settings) -> None:
    route = respx.get(CHANNELS_URL).mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "message": "quota exceeded",
                    "errors": [{"reason": "quotaExceeded"}],
                }
            },
        )
    )
    client = make_client(settings)

    with pytest.raises(YouTubeError, match="quota exceeded"):
        client.resolve_channel("test")

    assert route.call_count == 1
    assert client.ledger.used_today() == 0


@respx.mock
def test_refuses_to_exceed_budget(settings: Settings) -> None:
    route = respx.get(CHANNELS_URL).mock(return_value=httpx.Response(200, json=channel_payload()))
    client = make_client(settings)
    client.ledger.record("channels", settings.quota_budget, "test")

    with pytest.raises(QuotaExceeded):
        client.resolve_channel("test")

    assert route.call_count == 0


@respx.mock
def test_list_upload_ids_paginates_and_dedupes(settings: Settings) -> None:
    respx.get(PLAYLIST_URL).mock(
        side_effect=[
            httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "a"}},
                        {"contentDetails": {"videoId": "b"}},
                    ],
                    "nextPageToken": "next",
                },
            ),
            httpx.Response(
                200,
                json={
                    "items": [
                        {"contentDetails": {"videoId": "b"}},
                        {"contentDetails": {"videoId": "c"}},
                    ]
                },
            ),
        ]
    )
    client = make_client(settings)

    assert client.list_upload_ids("UU123") == ["a", "b", "c"]


@respx.mock
def test_list_upload_ids_stops_at_max(settings: Settings) -> None:
    respx.get(PLAYLIST_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {"contentDetails": {"videoId": "a"}},
                    {"contentDetails": {"videoId": "b"}},
                    {"contentDetails": {"videoId": "c"}},
                ]
            },
        )
    )
    client = make_client(settings)

    assert client.list_upload_ids("UU123", max_videos=2) == ["a", "b"]


@respx.mock
def test_fetch_videos_batches_and_builds_snapshots(settings: Settings) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["id"].split(",")
        return httpx.Response(200, json={"items": [video_item(video_id) for video_id in ids]})

    route = respx.get(VIDEOS_URL).mock(side_effect=handler)
    client = make_client(settings)
    ids = [str(index) for index in range(51)]

    batch = client.fetch_videos(ids)

    assert route.call_count == 2
    assert len(batch.videos) == 51
    assert len(batch.snapshots) == 51
    assert batch.snapshots[0].view_count == 10


@respx.mock
def test_comments_disabled_is_not_fatal(settings: Settings) -> None:
    respx.get(COMMENTS_URL).mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "message": "The video does not allow comments.",
                    "errors": [{"reason": "commentsDisabled"}],
                }
            },
        )
    )
    client = make_client(settings)

    assert client.fetch_comments("abc") == []
