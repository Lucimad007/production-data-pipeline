with ranked as (
    select
        *,
        row_number() over (
            partition by video_id
            order by snapshot_at desc
        ) as row_num
    from {{ source('bronze', 'video_snapshots') }}
)

select
    video_id,
    channel_id,
    snapshot_at,
    view_count,
    like_count,
    comment_count,
    ingested_at
from ranked
where row_num = 1
