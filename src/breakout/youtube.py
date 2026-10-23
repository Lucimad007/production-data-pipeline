"""YouTube Data API client with quota accounting, retries, and typed output."""

from __future__ import annotations

import contextlib
import json
import random
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import structlog

from breakout.config import Settings, get_settings
from breakout.contracts import (
    ApiEnvelope,
    Channel,
    ChannelSnapshot,
    Comment,
    Video,
    VideoSnapshot,
    payload_hash,
    request_hash,
    utc_now,
)

log = structlog.get_logger(__name__)

API_ROOT = "https://www.googleapis.com/youtube/v3"
QUOTA_COSTS: dict[str, int] = {
    "channels": 1,
    "playlistItems": 1,
    "videos": 1,
    "commentThreads": 1,
    "comments": 1,
    "search": 100,
}
BATCH_SIZE = 50


class YouTubeError(RuntimeError):
    """A non-retryable API or configuration error."""


class QuotaExceeded(YouTubeError):
    """The next call would exceed the configured daily quota budget."""


@dataclass
class QuotaStatus:
    used: int
    budget: int

    @property
    def remaining(self) -> int:
        return max(0, self.budget - self.used)


class QuotaLedger:
    """SQLite-backed daily quota accounting.

    YouTube's quota is the real constraint on this pipeline. Tracking it in a
    small operational database, separate from the lakehouse, keeps the budget
    enforceable even when the analytical store is being rebuilt.
    """

    def __init__(self, path: Path, daily_budget: int) -> None:
        self.path = path
        self.daily_budget = daily_budget
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS quota_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    units INTEGER NOT NULL,
                    used_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_quota_used_at ON quota_usage (used_at)"
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def used_today(self) -> int:
        today = datetime.now(UTC).date().isoformat()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(SUM(units), 0) FROM quota_usage WHERE substr(used_at, 1, 10) = ?",
                (today,),
            ).fetchone()
        return int(row[0])

    def status(self) -> QuotaStatus:
        return QuotaStatus(used=self.used_today(), budget=self.daily_budget)

    def can_spend(self, units: int) -> bool:
        return self.used_today() + units <= self.daily_budget

    def record(self, endpoint: str, units: int, run_id: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO quota_usage (run_id, endpoint, units, used_at) VALUES (?, ?, ?, ?)",
                (run_id, endpoint, units, utc_now().isoformat()),
            )
            connection.commit()


@dataclass(frozen=True)
class QuarantinedItem:
    endpoint: str
    item_index: int
    item_id: str | None
    reason: str
    payload_hash: str


@dataclass
class VideoBatch:
    videos: list[Video] = field(default_factory=list)
    snapshots: list[VideoSnapshot] = field(default_factory=list)
    rejected: list[QuarantinedItem] = field(default_factory=list)


@dataclass
class Collection:
    channel: Channel
    channel_snapshot: ChannelSnapshot
    videos: list[Video]
    video_snapshots: list[VideoSnapshot]
    comments: list[Comment]
    quota_used: int
    envelopes: list[ApiEnvelope] = field(default_factory=list)
    quarantined: list[QuarantinedItem] = field(default_factory=list)


def _error_detail(payload: dict[str, Any]) -> str:
    error = payload.get("error", {})
    message = error.get("message", "unknown error")
    reasons = [item.get("reason", "") for item in error.get("errors", []) if item.get("reason")]
    return f"{message} ({', '.join(reasons)})" if reasons else str(message)


class YouTubeClient:
    def __init__(
        self,
        api_key: str,
        *,
        settings: Settings | None = None,
        http_client: httpx.Client | None = None,
        ledger: QuotaLedger | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise YouTubeError("YOUTUBE_API_KEY is not set. Add it to .env or the environment.")
        self.api_key = api_key.strip()
        self.settings = settings or get_settings()
        self._http = http_client or httpx.Client(timeout=self.settings.request_timeout_seconds)
        self._owns_http = http_client is None
        self.ledger = ledger or QuotaLedger(
            self.settings.quota_db, self.settings.quota_budget
        )
        self._sleep = sleep
        self._last_request_at = 0.0
        self.run_id = utc_now().strftime("run-%Y%m%dT%H%M%SZ")
        self.envelopes: list[ApiEnvelope] = []

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> YouTubeClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _get(self, endpoint: str, **params: Any) -> ApiEnvelope:
        units = QUOTA_COSTS.get(endpoint, 1)
        if not self.ledger.can_spend(units):
            status = self.ledger.status()
            raise QuotaExceeded(
                f"{endpoint} needs {units} units; {status.used}/{status.budget} used today"
            )

        safe_params = {key: value for key, value in params.items() if value is not None}
        req_hash = request_hash(endpoint, safe_params)

        for attempt in range(self.settings.max_retries + 1):
            self._throttle()
            try:
                response = self._http.get(
                    f"{API_ROOT}/{endpoint}",
                    params={**safe_params, "key": self.api_key},
                    timeout=self.settings.request_timeout_seconds,
                )
            except httpx.TransportError as exc:
                if attempt >= self.settings.max_retries:
                    raise YouTubeError(f"{endpoint} transport failure: {exc}") from exc
                self._backoff(attempt)
                continue

            if response.status_code in {429, 500, 502, 503, 504}:
                if attempt >= self.settings.max_retries:
                    raise YouTubeError(
                        f"{endpoint} failed after {attempt + 1} attempts: "
                        f"HTTP {response.status_code}"
                    )
                retry_after = response.headers.get("Retry-After")
                self._backoff(attempt, retry_after=retry_after)
                continue

            if response.status_code >= 400:
                try:
                    detail = _error_detail(response.json())
                except (json.JSONDecodeError, ValueError):
                    detail = response.text[:300]
                raise YouTubeError(f"{endpoint} failed with HTTP {response.status_code}: {detail}")

            payload = response.json()
            self.ledger.record(endpoint, units, self.run_id)
            envelope = ApiEnvelope(
                endpoint=endpoint,
                params=safe_params,
                fetched_at=utc_now(),
                status_code=response.status_code,
                payload=payload,
                request_hash=req_hash,
                payload_hash=payload_hash(payload),
                units=units,
            )
            log.info(
                "youtube.request",
                endpoint=endpoint,
                status=response.status_code,
                units=units,
                attempt=attempt + 1,
            )
            self.envelopes.append(envelope)
            return envelope

        raise YouTubeError(f"{endpoint} exhausted retries")

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.settings.min_request_interval_seconds - elapsed
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = time.monotonic()

    def _backoff(self, attempt: int, retry_after: str | None = None) -> None:
        delay = min(2**attempt + random.uniform(0, 0.5), 30.0)
        if retry_after:
            with contextlib.suppress(ValueError):
                delay = max(delay, float(retry_after))
        log.warning("youtube.retry", attempt=attempt + 1, delay_seconds=round(delay, 2))
        self._sleep(delay)

    # -- endpoints ---------------------------------------------------------

    def resolve_channel(self, handle: str) -> Channel:
        identifier = handle.strip().lstrip("@")
        if not identifier:
            raise YouTubeError("Pass a channel handle or channel id.")
        params: dict[str, Any] = {"part": "snippet,contentDetails,statistics"}
        if identifier.startswith("UC") and len(identifier) == 24:
            params["id"] = identifier
        else:
            params["forHandle"] = identifier
        envelope = self._get("channels", **params)
        items = envelope.payload.get("items", [])
        if not items:
            raise YouTubeError(f"No channel found for {handle!r}.")
        return Channel.from_api(items[0])

    def list_upload_ids(self, playlist_id: str, max_videos: int = 0) -> list[str]:
        ids: list[str] = []
        seen: set[str] = set()
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {
                "part": "contentDetails",
                "playlistId": playlist_id,
                "maxResults": BATCH_SIZE,
            }
            if page_token:
                params["pageToken"] = page_token
            envelope = self._get("playlistItems", **params)
            for item in envelope.payload.get("items", []):
                video_id = item.get("contentDetails", {}).get("videoId")
                if not video_id or video_id in seen:
                    continue
                seen.add(video_id)
                ids.append(video_id)
                if max_videos and len(ids) >= max_videos:
                    return ids
            page_token = envelope.payload.get("nextPageToken")
            if not page_token:
                return ids

    def fetch_videos(self, video_ids: list[str]) -> VideoBatch:
        batch = VideoBatch()
        unique = list(dict.fromkeys(video_ids))
        for start in range(0, len(unique), BATCH_SIZE):
            chunk = unique[start : start + BATCH_SIZE]
            envelope = self._get(
                "videos",
                part="snippet,contentDetails,statistics",
                id=",".join(chunk),
                maxResults=len(chunk),
            )
            fetched_at = envelope.fetched_at
            for index, item in enumerate(envelope.payload.get("items", [])):
                try:
                    video = Video.from_api(item)
                except ValueError as exc:
                    batch.rejected.append(
                        QuarantinedItem(
                            endpoint="videos",
                            item_index=index,
                            item_id=item.get("id"),
                            reason=str(exc),
                            payload_hash=envelope.payload_hash,
                        )
                    )
                    log.warning(
                        "youtube.video_quarantined",
                        item_id=item.get("id"),
                        reason=str(exc),
                    )
                    continue
                stats = item.get("statistics", {})
                batch.videos.append(video)
                batch.snapshots.append(
                    VideoSnapshot(
                        video_id=video.video_id,
                        channel_id=video.channel_id,
                        snapshot_at=fetched_at,
                        view_count=_int_or_none(stats.get("viewCount")),
                        like_count=_int_or_none(stats.get("likeCount")),
                        comment_count=_int_or_none(stats.get("commentCount")),
                    )
                )
        return batch

    def fetch_comments(self, video_id: str, max_results: int = 20) -> list[Comment]:
        comments: list[Comment] = []
        page_token: str | None = None
        while len(comments) < max_results:
            params: dict[str, Any] = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": min(100, max_results - len(comments)),
                "order": "relevance",
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                envelope = self._get("commentThreads", **params)
            except YouTubeError as exc:
                if "commentsDisabled" in str(exc):
                    log.info("youtube.comments_disabled", video_id=video_id)
                    return comments
                raise
            for item in envelope.payload.get("items", []):
                comment = Comment.from_thread(item, video_id)
                if comment:
                    comments.append(comment)
            page_token = envelope.payload.get("nextPageToken")
            if not page_token:
                break
        return comments

    def collect(
        self,
        handle: str,
        *,
        max_videos: int = 0,
        comment_video_limit: int = 0,
        max_comments_per_video: int = 20,
    ) -> Collection:
        started_used = self.ledger.status().used
        started_envelopes = len(self.envelopes)
        channel = self.resolve_channel(handle)
        upload_ids = self.list_upload_ids(channel.uploads_playlist, max_videos)
        batch = self.fetch_videos(upload_ids)
        snapshot_at = utc_now()
        channel_snapshot = ChannelSnapshot(
            channel_id=channel.channel_id,
            snapshot_at=snapshot_at,
            title=channel.title,
            handle=channel.handle,
            subscriber_count=channel.subscriber_count,
            video_count=channel.video_count,
            view_count=channel.view_count,
            uploads_playlist=channel.uploads_playlist,
        )
        comments: list[Comment] = []
        if comment_video_limit:
            ranked = sorted(
                batch.snapshots,
                key=lambda item: item.view_count or 0,
                reverse=True,
            )[:comment_video_limit]
            for snapshot in ranked:
                comments.extend(self.fetch_comments(snapshot.video_id, max_comments_per_video))
        return Collection(
            channel=channel,
            channel_snapshot=channel_snapshot,
            videos=batch.videos,
            video_snapshots=batch.snapshots,
            comments=comments,
            quota_used=self.ledger.status().used - started_used,
            envelopes=self.envelopes[started_envelopes:],
            quarantined=batch.rejected,
        )


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
