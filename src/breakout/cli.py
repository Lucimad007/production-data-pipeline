"""Command line entry point for local runs."""

from __future__ import annotations

import argparse
import sys

import structlog

from breakout.config import Settings, get_settings
from breakout.storage import Lakehouse, RawLanding
from breakout.youtube import QuotaExceeded, YouTubeClient, YouTubeError

log = structlog.get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="breakout",
        description="Creator growth intelligence lakehouse",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="Pull a channel, videos, snapshots, and comments")
    ingest.add_argument("--channel", help="Channel handle or UC id")
    ingest.add_argument("--max-videos", type=int, help="Newest N uploads; 0 means all")
    ingest.add_argument("--comment-videos", type=int, help="Only fetch comments for the top N videos")
    ingest.add_argument("--max-comments", type=int, help="Comments per video")

    sub.add_parser("status", help="Show bronze row counts and quota usage")

    return parser


def run_ingest(args: argparse.Namespace, settings: Settings) -> int:
    channel = args.channel or settings.channel_handle
    max_videos = settings.max_videos if args.max_videos is None else args.max_videos
    comment_videos = (
        settings.comment_video_limit
        if args.comment_videos is None
        else args.comment_videos
    )
    max_comments = (
        settings.max_comments_per_video if args.max_comments is None else args.max_comments
    )

    with YouTubeClient(settings.youtube_api_key, settings=settings) as client:
        collection = client.collect(
            channel,
            max_videos=max_videos,
            comment_video_limit=comment_videos,
            max_comments_per_video=max_comments,
        )

    landing = RawLanding(settings.raw_dir)
    for envelope in collection.envelopes:
        landing.write(envelope)

    with Lakehouse(settings) as lake:
        lake.write_api_responses(collection.envelopes)
        written = lake.write_collection(collection)
        totals = lake.table_counts()

    print(f"channel={collection.channel.title} id={collection.channel.channel_id}")
    print(f"videos={len(collection.videos)} comments={len(collection.comments)}")
    print(f"quota_units={collection.quota_used}")
    print("written=" + " ".join(f"{key}:{value}" for key, value in written.items()))
    print("bronze=" + " ".join(f"{key}:{value}" for key, value in totals.items()))
    return 0


def run_status(settings: Settings) -> int:
    with Lakehouse(settings) as lake:
        totals = lake.table_counts()
        freshness = lake.query_df(
            "SELECT MAX(snapshot_at) AS latest_snapshot FROM lake.bronze.video_snapshots"
        )
    print("bronze=" + " ".join(f"{key}:{value}" for key, value in totals.items()))
    if not freshness.empty and freshness.loc[0, "latest_snapshot"] is not None:
        print(f"latest_snapshot={freshness.loc[0, 'latest_snapshot']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(settings.log_level.upper())
    )
    parser = build_parser()
    args = parser.parse_args(argv)

    if not settings.youtube_api_key and args.command == "ingest":
        print("Set YOUTUBE_API_KEY in .env or the environment.", file=sys.stderr)
        return 2

    try:
        if args.command == "ingest":
            return run_ingest(args, settings)
        if args.command == "status":
            return run_status(settings)
    except QuotaExceeded as exc:
        print(f"Quota budget reached: {exc}", file=sys.stderr)
        return 3
    except YouTubeError as exc:
        print(f"YouTube API error: {exc}", file=sys.stderr)
        return 4

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
