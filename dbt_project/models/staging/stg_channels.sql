with ranked as (
    select
        *,
        row_number() over (
            partition by channel_id
            order by snapshot_at desc, ingested_at desc
        ) as row_num
    from {{ source('bronze', 'channels') }}
)

select
    channel_id,
    snapshot_at,
    title,
    handle,
    subscriber_count,
    video_count,
    view_count,
    uploads_playlist
from ranked
where row_num = 1
