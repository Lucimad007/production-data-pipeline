with history as (
    select
        video_id,
        channel_id,
        snapshot_at,
        view_count,
        like_count,
        comment_count,
        lag(view_count) over (
            partition by video_id
            order by snapshot_at
        ) as previous_view_count,
        lag(snapshot_at) over (
            partition by video_id
            order by snapshot_at
        ) as previous_snapshot_at
    from {{ source('bronze', 'video_snapshots') }}
)

select
    video_id,
    channel_id,
    snapshot_at,
    view_count,
    like_count,
    comment_count,
    previous_view_count,
    previous_snapshot_at,
    view_count - previous_view_count as delta_views,
    {{ date_diff_compat('minute', 'previous_snapshot_at', 'snapshot_at') }} / 60.0
        as hours_since_previous,
    case
        when previous_view_count is not null
         and {{ date_diff_compat('minute', 'previous_snapshot_at', 'snapshot_at') }} > 0
            then (view_count - previous_view_count)::double
                / ({{ date_diff_compat('minute', 'previous_snapshot_at', 'snapshot_at') }} / 60.0)
    end as views_per_hour
from history
