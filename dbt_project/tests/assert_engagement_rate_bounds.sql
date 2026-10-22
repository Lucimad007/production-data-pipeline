select *
from {{ ref('mart_video_performance') }}
where engagement_rate < 0
   or engagement_rate > 1
   or like_rate < 0
   or like_rate > 1
   or comment_rate < 0
   or comment_rate > 1
