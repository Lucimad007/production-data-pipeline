{% snapshot dim_video %}

{{
    config(
        target_schema='silver',
        unique_key='video_id',
        strategy='check',
        check_cols=['title', 'description', 'duration_seconds', 'category_id'],
    )
}}

select
    video_id,
    channel_id,
    title,
    description,
    published_at,
    duration_seconds,
    category_id,
    live_broadcast_content,
    default_language,
    thumbnail_url
from {{ ref('stg_videos') }}

{% endsnapshot %}
