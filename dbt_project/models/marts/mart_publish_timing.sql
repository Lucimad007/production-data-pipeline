with performance as (
    select * from {{ ref('mart_video_performance') }}
)

select
    channel_id,
    publish_dow,
    publish_hour,
    count(*) as videos,
    median(views_per_day) as median_views_per_day,
    median(breakout_score) as median_breakout_score,
    avg(engagement_rate) as avg_engagement_rate,
    count_if(performance_label = 'breakout')::double / count(*) as breakout_rate
from performance
group by 1, 2, 3
having count(*) >= 3
