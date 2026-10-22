from __future__ import annotations

from pathlib import Path

import pytest

from breakout.config import Settings


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        youtube_api_key="test-key",
        data_dir=tmp_path,
        raw_dir=tmp_path / "raw",
        duckdb_path=tmp_path / "breakout.duckdb",
        ducklake_catalog=tmp_path / "catalog.sqlite",
        ducklake_data=tmp_path / "lake",
        quota_db=tmp_path / "quota.sqlite",
        daily_quota_units=100,
        quota_budget_pct=1.0,
        min_request_interval_seconds=0.0,
        max_retries=3,
    )
