with performance as (
    select * from {{ ref('mart_video_performance') }}
),

channels as (
    select * from {{ ref('stg_channels') }}
)

select
    c.channel_id,
    c.title,
    c.handle,
    c.subscriber_count,
    c.video_count as channel_video_count,
    c.view_count as channel_view_count,
    c.snapshot_at as channel_snapshot_at,
    count(p.video_id) as videos_analyzed,
    sum(p.view_count) as total_views,
    median(p.views_per_day) as median_views_per_day,
    median(p.engagement_rate) as median_engagement_rate,
    count_if(p.performance_label = 'breakout') as breakout_count,
    count_if(p.performance_label = 'underperformer') as underperformer_count,
    max(p.snapshot_at) as latest_video_snapshot_at
from channels c
left join performance p
    on c.channel_id = p.channel_id
group by 1, 2, 3, 4, 5, 6, 7
