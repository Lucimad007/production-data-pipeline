"""Dagster definitions: the operating surface for Breakout."""

from dagster import (
    AssetCheckResult,
    Config,
    Definitions,
    Failure,
    MaterializeResult,
    ScheduleDefinition,
    asset,
    asset_check,
    define_asset_job,
)

from breakout.config import get_settings
from breakout.pipeline import (
    bronze_counts,
    build_models,
    ingest_channel,
    latest_snapshot,
    mart_counts,
    quota_status,
)


class IngestConfig(Config):
    channel: str = "AlexHormozi"
    max_videos: int = 500
    comment_videos: int = 20
    max_comments: int = 20


@asset(group_name="ingestion", compute_kind="python")
def ingest(config: IngestConfig) -> MaterializeResult:
    """Pull the channel, preserve raw responses, and upsert bronze."""
    settings = get_settings()
    result = ingest_channel(
        settings,
        config.channel,
        max_videos=config.max_videos,
        comment_videos=config.comment_videos,
        max_comments=config.max_comments,
    )
    return MaterializeResult(
        metadata={
            "channel": result.channel_title,
            "channel_id": result.channel_id,
            "videos": result.videos,
            "snapshots": result.snapshots,
            "comments": result.comments,
            "quota_units": result.quota_used,
            "raw_files": result.raw_files,
            "bronze_videos": result.bronze["videos"],
            "bronze_snapshots": result.bronze["video_snapshots"],
        }
    )


@asset(deps=[ingest], group_name="transformation", compute_kind="dbt")
def dbt_models() -> MaterializeResult:
    """Build and test every dbt model."""
    settings = get_settings()
    if not build_models(settings):
        raise Failure(description="dbt build failed; see the captured dbt logs.")
    counts = mart_counts(settings)
    return MaterializeResult(
        metadata={**counts, "latest_snapshot": latest_snapshot(settings) or "none"}
    )


@asset(deps=[dbt_models], group_name="observability", compute_kind="python")
def pipeline_health() -> MaterializeResult:
    """Expose the operational state the dashboard and on-call runbook need."""
    settings = get_settings()
    quota = quota_status(settings)
    bronze = bronze_counts(settings)
    marts = mart_counts(settings)
    return MaterializeResult(
        metadata={
            **{f"bronze_{key}": value for key, value in bronze.items()},
            **{f"mart_{key}": value for key, value in marts.items()},
            "latest_snapshot": latest_snapshot(settings) or "none",
            "quota_used": quota.used,
            "quota_budget": quota.budget,
        }
    )


@asset_check(asset=ingest, description="Bronze must contain videos and snapshots after a run.")
def bronze_rows_present() -> AssetCheckResult:
    counts = bronze_counts(get_settings())
    total = counts["videos"] + counts["video_snapshots"]
    return AssetCheckResult(
        passed=total > 0,
        metadata={"videos": counts["videos"], "video_snapshots": counts["video_snapshots"]},
    )


@asset_check(asset=ingest, description="The run must stay inside the daily quota budget.")
def quota_within_budget() -> AssetCheckResult:
    quota = quota_status(get_settings())
    return AssetCheckResult(
        passed=quota.used <= quota.budget,
        metadata={"used": quota.used, "budget": quota.budget},
    )


@asset_check(asset=dbt_models, description="The primary mart must not be empty.")
def marts_present() -> AssetCheckResult:
    counts = mart_counts(get_settings())
    return AssetCheckResult(
        passed=counts.get("mart_video_performance", 0) > 0,
        metadata={key: value for key, value in counts.items()},
    )


daily_refresh = define_asset_job(
    "daily_refresh",
    selection=[ingest, dbt_models, pipeline_health],
    description="Pull the latest channel data, rebuild marts, and record health.",
)

daily_schedule = ScheduleDefinition(
    name="daily_refresh_schedule",
    job=daily_refresh,
    cron_schedule="0 6 * * *",
    execution_timezone="UTC",
)

defs = Definitions(
    assets=[ingest, dbt_models, pipeline_health],
    asset_checks=[bronze_rows_present, quota_within_budget, marts_present],
    schedules=[daily_schedule],
)
