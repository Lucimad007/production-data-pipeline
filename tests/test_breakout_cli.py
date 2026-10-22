from __future__ import annotations

from breakout.cli import build_parser


def test_ingest_defaults_are_optional() -> None:
    args = build_parser().parse_args(["ingest"])
    assert args.command == "ingest"
    assert args.channel is None
    assert args.max_videos is None
    assert args.comment_videos is None
    assert args.max_comments is None


def test_build_command() -> None:
    args = build_parser().parse_args(["build"])
    assert args.command == "build"


def test_dashboard_command() -> None:
    args = build_parser().parse_args(["dashboard"])
    assert args.command == "dashboard"


def test_health_command() -> None:
    args = build_parser().parse_args(["health", "--json"])
    assert args.command == "health"
    assert args.json is True


def test_ingest_accepts_overrides() -> None:
    args = build_parser().parse_args(
        [
            "ingest",
            "--channel",
            "@test",
            "--max-videos",
            "50",
            "--comment-videos",
            "5",
            "--max-comments",
            "10",
        ]
    )
    assert args.channel == "@test"
    assert args.max_videos == 50
    assert args.comment_videos == 5
    assert args.max_comments == 10
