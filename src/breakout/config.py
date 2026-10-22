"""Configuration and filesystem layout."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings, loaded from the environment and `.env`."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    youtube_api_key: str = ""
    channel_handle: str = "AlexHormozi"
    max_videos: int = 500
    comment_video_limit: int = 20
    max_comments_per_video: int = 20

    data_dir: Path = PROJECT_ROOT / "data"
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    duckdb_path: Path = PROJECT_ROOT / "data" / "breakout.duckdb"
    ducklake_catalog: Path = PROJECT_ROOT / "data" / "breakout_catalog.sqlite"
    ducklake_data: Path = PROJECT_ROOT / "data" / "lake"
    quota_db: Path = PROJECT_ROOT / "data" / "quota.sqlite"
    dbt_project_dir: Path = PROJECT_ROOT / "dbt_project"
    dbt_profiles_dir: Path = PROJECT_ROOT / "dbt_project"

    daily_quota_units: int = 10_000
    quota_budget_pct: float = Field(default=0.8, ge=0.1, le=1.0)
    request_timeout_seconds: float = 30.0
    max_retries: int = 4
    min_request_interval_seconds: float = 0.05
    log_level: str = "INFO"

    @property
    def quota_budget(self) -> int:
        return int(self.daily_quota_units * self.quota_budget_pct)

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.raw_dir, self.ducklake_data):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
