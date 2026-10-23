"""Governed metric registry.

The agent surface is intentionally small: every metric is authored in YAML,
owned, and executed as a read-only query. There is no raw text-to-SQL path.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from breakout.config import PROJECT_ROOT, Settings
from breakout.storage import Lakehouse

METRICS_DIR = PROJECT_ROOT / "metrics"
DEFAULT_LIMIT = 100
MAX_LIMIT = 1_000


class MetricError(ValueError):
    """A registry definition is invalid or missing."""


class UnknownMetric(MetricError):
    """The caller asked for a metric that is not registered."""


@dataclass(frozen=True)
class Metric:
    name: str
    description: str
    grain: str
    owner: str
    sql: str
    dimensions: tuple[str, ...]
    examples: tuple[str, ...]

    def summary(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "grain": self.grain,
            "owner": self.owner,
            "dimensions": list(self.dimensions),
            "examples": list(self.examples),
        }

    def detail(self) -> dict[str, Any]:
        return {**self.summary(), "sql": self.sql}


@lru_cache(maxsize=8)
def load_metrics(directory: str | Path = METRICS_DIR) -> dict[str, Metric]:
    metrics: dict[str, Metric] = {}
    paths = sorted(Path(directory).glob("*.yml"))
    if not paths:
        raise MetricError(f"No metric definitions found in {directory}")

    for path in paths:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for index, item in enumerate(payload.get("metrics", [])):
            try:
                name = str(item["name"]).strip()
                description = str(item["description"]).strip()
                grain = str(item["grain"]).strip()
                owner = str(item["owner"]).strip()
                sql = str(item["sql"]).strip().rstrip(";")
            except KeyError as exc:
                raise MetricError(f"{path.name}: metric {index} is missing {exc}") from exc
            if not name or not name.replace("_", "").isalnum():
                raise MetricError(f"{path.name}: invalid metric name {name!r}")
            if name in metrics:
                raise MetricError(f"{path.name}: duplicate metric {name!r}")
            if not sql:
                raise MetricError(f"{path.name}: metric {name!r} has no SQL")
            metrics[name] = Metric(
                name=name,
                description=description,
                grain=grain,
                owner=owner,
                sql=sql,
                dimensions=tuple(item.get("dimensions") or []),
                examples=tuple(item.get("examples") or []),
            )

    if not metrics:
        raise MetricError(f"No metrics defined in {directory}")
    return metrics


def list_metrics(directory: str | Path = METRICS_DIR) -> list[dict[str, Any]]:
    return [metric.summary() for metric in load_metrics(directory).values()]


def describe_metric(name: str, directory: str | Path = METRICS_DIR) -> dict[str, Any]:
    metrics = load_metrics(directory)
    try:
        metric = metrics[name]
    except KeyError as exc:
        raise UnknownMetric(
            f"Unknown metric {name!r}. Available: {', '.join(sorted(metrics))}"
        ) from exc
    return metric.detail()


def query_metric(
    name: str,
    limit: int = DEFAULT_LIMIT,
    *,
    settings: Settings | None = None,
    directory: str | Path = METRICS_DIR,
) -> pd.DataFrame:
    """Execute a registered metric with a bounded row limit.

    The SQL comes from the authored registry, never from the caller. The only
    caller-controlled value is an integer limit, which is clamped before it is
    interpolated.
    """
    metrics = load_metrics(directory)
    try:
        metric = metrics[name]
    except KeyError as exc:
        raise UnknownMetric(
            f"Unknown metric {name!r}. Available: {', '.join(sorted(metrics))}"
        ) from exc

    safe_limit = max(1, min(int(limit), MAX_LIMIT))
    sql = f"select * from ({metric.sql}) as metric_result limit {safe_limit}"
    with Lakehouse(settings) as lake:
        return lake.query_df(sql)
