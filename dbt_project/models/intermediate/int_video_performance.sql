with videos as (
    select * from {{ ref('stg_videos') }}
),

latest as (
    select * from {{ ref('stg_video_snapshots') }}
),

topics as (
    select * from {{ ref('int_video_topics') }}
),

base as (
    select
        v.video_id,
        v.channel_id,
        v.title,
        v.description,
        v.published_at,
        v.duration_seconds,
        v.category_id,
        v.live_broadcast_content,
        v.thumbnail_url,
        t.topic,
        s.snapshot_at,
        s.view_count,
        s.like_count,
        s.comment_count,
        date_diff('day', v.published_at, s.snapshot_at) as age_days,
        date_diff('hour', v.published_at, s.snapshot_at) as age_hours,
        case
            when date_diff('day', v.published_at, s.snapshot_at) <= 7 then '0-7'
            when date_diff('day', v.published_at, s.snapshot_at) <= 30 then '8-30'
            when date_diff('day', v.published_at, s.snapshot_at) <= 90 then '31-90'
            when date_diff('day', v.published_at, s.snapshot_at) <= 365 then '91-365'
            else '365+'
        end as age_bucket,
        ln(1 + greatest(coalesce(s.view_count, 0), 0)) as log_views,
        coalesce(s.view_count, 0)::double
            / greatest(date_diff('day', v.published_at, s.snapshot_at), 1) as views_per_day,
        coalesce(s.view_count, 0)::double
            / greatest(date_diff('hour', v.published_at, s.snapshot_at), 1) as views_per_hour,
        case
            when coalesce(s.view_count, 0) > 0
                then (coalesce(s.like_count, 0) + coalesce(s.comment_count, 0))::double
                    / s.view_count
        end as engagement_rate,
        case
            when coalesce(s.view_count, 0) > 0
                then coalesce(s.like_count, 0)::double / s.view_count
        end as like_rate,
        case
            when coalesce(s.view_count, 0) > 0
                then coalesce(s.comment_count, 0)::double / s.view_count
        end as comment_rate,
        dayname(v.published_at) as publish_dow,
        extract(hour from v.published_at) as publish_hour,
        case when v.duration_seconds <= 60 then true else false end as is_short
    from videos v
    join latest s
        on v.video_id = s.video_id
    left join topics t
        on v.video_id = t.video_id
    where v.published_at is not null
      and s.snapshot_at >= v.published_at
),

medians as (
    select
        channel_id,
        age_bucket,
        median(log_views) as median_log_views
    from base
    group by 1, 2
),

deviations as (
    select
        b.channel_id,
        b.age_bucket,
        median(abs(b.log_views - m.median_log_views)) as mad_log_views
    from base b
    join medians m
        on b.channel_id = m.channel_id
       and b.age_bucket = m.age_bucket
    group by 1, 2
),

scored as (
    select
        b.*,
        m.median_log_views,
        d.mad_log_views,
        (b.log_views - m.median_log_views)
            / greatest(1.4826 * d.mad_log_views, 0.05) as breakout_score
    from base b
    join medians m
        on b.channel_id = m.channel_id
       and b.age_bucket = m.age_bucket
    join deviations d
        on b.channel_id = d.channel_id
       and b.age_bucket = d.age_bucket
)

select
    *,
    case
        when breakout_score >= 2 then 'breakout'
        when breakout_score <= -1 then 'underperformer'
        else 'typical'
    end as performance_label
from scored
