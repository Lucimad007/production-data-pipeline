select *
from {{ ref('mart_video_performance') }}
where view_count < 0
   or like_count < 0
   or comment_count < 0
