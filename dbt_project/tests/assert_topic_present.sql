select *
from {{ ref('mart_video_performance') }}
where topic is null
   or trim(topic) = ''
