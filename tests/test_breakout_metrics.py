from __future__ import annotations

import pytest

from breakout.metrics import (
    MAX_LIMIT,
    MetricError,
    UnknownMetric,
    describe_metric,
    list_metrics,
    load_metrics,
    query_metric,
)


def test_registry_exposes_core_metrics() -> None:
    names = {metric["name"] for metric in list_metrics()}
    assert {
        "channel_overview",
        "breakout_rate",
        "top_breakouts",
        "topic_performance",
        "publish_timing",
        "engagement_summary",
        "data_freshness",
        "quarantine_summary",
    } <= names


def test_describe_returns_definition_and_sql() -> None:
    metric = describe_metric("breakout_rate")
    assert metric["grain"] == "channel"
    assert metric["owner"] == "creator-intelligence"
    assert "breakout" in metric["description"].lower()
    assert "mart_video_performance" in metric["sql"]
    assert metric["dimensions"] == ["channel_id"]


def test_unknown_metric_raises_with_choices() -> None:
    with pytest.raises(UnknownMetric, match="Available"):
        describe_metric("not_a_metric")


def test_empty_registry_is_an_error(tmp_path) -> None:
    with pytest.raises(MetricError, match="No metric definitions"):
        load_metrics(tmp_path)


def test_query_metric_returns_a_bounded_frame(settings) -> None:
    frame = query_metric("quarantine_summary", limit=5, settings=settings)
    assert len(frame) == 1
    assert int(frame.loc[0, "quarantine_count"]) == 0


def test_limit_is_clamped_to_the_registry_maximum(settings) -> None:
    frame = query_metric("data_freshness", limit=MAX_LIMIT + 10_000, settings=settings)
    assert len(frame) == 1
    assert "latest_snapshot" in frame.columns
