select *
from {{ ref('mart_video_performance') }}
where published_at > snapshot_at
