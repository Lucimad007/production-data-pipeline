select
    video_id,
    channel_id,
    title,
    description,
    published_at,
    duration_iso,
    duration_seconds,
    tags_json,
    category_id,
    live_broadcast_content,
    default_language,
    thumbnail_url,
    ingested_at
from {{ source('bronze', 'videos') }}
qualify row_number() over (partition by video_id order by ingested_at desc) = 1
