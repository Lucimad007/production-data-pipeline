select
    video_id,
    channel_id,
    title,
    topic,
    published_at,
    snapshot_at,
    age_days,
    age_hours,
    age_bucket,
    view_count,
    like_count,
    comment_count,
    views_per_day,
    views_per_hour,
    engagement_rate,
    like_rate,
    comment_rate,
    log_views,
    median_log_views,
    mad_log_views,
    breakout_score,
    performance_label,
    duration_seconds,
    is_short,
    publish_dow,
    publish_hour,
    thumbnail_url,
    rank() over (
        partition by channel_id
        order by breakout_score desc
    ) as breakout_rank,
    percent_rank() over (
        partition by channel_id
        order by views_per_day
    ) as views_per_day_percentile
from {{ ref('int_video_performance') }}
