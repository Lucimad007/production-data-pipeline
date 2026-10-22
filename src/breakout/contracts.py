"""Typed contracts at the API boundary.

The raw payload is always preserved. These models are the *interpreted* view:
the fields the warehouse is allowed to rely on. If YouTube adds or removes a
field, the parser fails loudly in tests and quarantines in production.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_DURATION = re.compile(
    r"^P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$"
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_duration_seconds(value: str | None) -> int | None:
    if not value:
        return None
    match = _DURATION.match(value)
    if not match:
        return None
    days = int(match.group("days") or 0)
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return days * 86_400 + hours * 3_600 + minutes * 60 + seconds


def canonical_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def request_hash(endpoint: str, params: dict[str, Any]) -> str:
    safe = {key: value for key, value in params.items() if key.lower() != "key"}
    return sha256_text(f"{endpoint}?{canonical_json(safe)}")


def payload_hash(payload: Any) -> str:
    return sha256_text(canonical_json(payload))


def author_hash(channel_id: str | None, display_name: str | None) -> str:
    return sha256_text(channel_id or display_name or "unknown")


class Channel(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_id: str
    title: str
    handle: str | None = None
    published_at: datetime | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    uploads_playlist: str

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> Channel:
        snippet = item.get("snippet", {})
        statistics = item.get("statistics", {})
        uploads = item.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not item.get("id") or not uploads:
            raise ValueError("channel payload is missing id or uploads playlist")
        return cls(
            channel_id=item["id"],
            title=snippet.get("title", ""),
            handle=snippet.get("customUrl"),
            published_at=parse_datetime(snippet.get("publishedAt")),
            subscriber_count=parse_int(statistics.get("subscriberCount")),
            video_count=parse_int(statistics.get("videoCount")),
            view_count=parse_int(statistics.get("viewCount")),
            uploads_playlist=uploads,
        )


class Video(BaseModel):
    model_config = ConfigDict(frozen=True)

    video_id: str
    channel_id: str
    title: str
    description: str = ""
    published_at: datetime | None = None
    duration_iso: str | None = None
    duration_seconds: int | None = None
    tags: list[str] = Field(default_factory=list)
    category_id: str | None = None
    live_broadcast_content: str | None = None
    default_language: str | None = None
    thumbnail_url: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _tags(cls, value: Any) -> list[str]:
        return list(value or [])

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> Video:
        snippet = item.get("snippet", {})
        details = item.get("contentDetails", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (thumbnails.get("maxres") or thumbnails.get("high") or thumbnails.get("default") or {})
        if not item.get("id") or not snippet.get("title"):
            raise ValueError("video payload is missing id or title")
        return cls(
            video_id=item["id"],
            channel_id=snippet.get("channelId", ""),
            title=snippet["title"],
            description=snippet.get("description", ""),
            published_at=parse_datetime(snippet.get("publishedAt")),
            duration_iso=details.get("duration"),
            duration_seconds=parse_duration_seconds(details.get("duration")),
            tags=snippet.get("tags", []),
            category_id=snippet.get("categoryId"),
            live_broadcast_content=snippet.get("liveBroadcastContent"),
            default_language=snippet.get("defaultAudioLanguage"),
            thumbnail_url=thumbnail.get("url"),
        )


class ChannelSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel_id: str
    snapshot_at: datetime
    title: str
    handle: str | None = None
    subscriber_count: int | None = None
    video_count: int | None = None
    view_count: int | None = None
    uploads_playlist: str


class VideoSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True)

    video_id: str
    channel_id: str
    snapshot_at: datetime
    view_count: int | None = None
    like_count: int | None = None
    comment_count: int | None = None


class Comment(BaseModel):
    model_config = ConfigDict(frozen=True)

    comment_id: str
    video_id: str
    author_hash: str
    text: str
    like_count: int | None = None
    published_at: datetime | None = None
    updated_at: datetime | None = None
    parent_id: str | None = None

    @classmethod
    def from_thread(cls, item: dict[str, Any], video_id: str) -> Comment | None:
        snippet = item.get("snippet", {})
        top = snippet.get("topLevelComment", {})
        top_snippet = top.get("snippet", {})
        comment_id = top.get("id") or item.get("id")
        if not comment_id or not top_snippet.get("textDisplay"):
            return None
        author_channel = top_snippet.get("authorChannelId", {}).get("value")
        return cls(
            comment_id=comment_id,
            video_id=video_id,
            author_hash=author_hash(author_channel, top_snippet.get("authorDisplayName")),
            text=top_snippet["textDisplay"],
            like_count=parse_int(top_snippet.get("likeCount")),
            published_at=parse_datetime(top_snippet.get("publishedAt")),
            updated_at=parse_datetime(top_snippet.get("updatedAt")),
            parent_id=None,
        )


class ApiEnvelope(BaseModel):
    """One immutable API request and its response."""

    model_config = ConfigDict(frozen=True)

    endpoint: str
    params: dict[str, Any]
    fetched_at: datetime
    status_code: int
    payload: dict[str, Any]
    request_hash: str
    payload_hash: str
    units: int
