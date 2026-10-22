with videos as (
    select
        video_id,
        lower(coalesce(title, '') || ' ' || coalesce(description, '')) as search_text
    from {{ ref('stg_videos') }}
),

rules as (
    select topic, pattern, priority
    from {{ ref('topic_rules') }}
    where pattern is not null
      and pattern <> ''
),

matches as (
    select
        v.video_id,
        r.topic,
        r.priority,
        row_number() over (partition by v.video_id order by r.priority) as row_num
    from videos v
    join rules r
        on regexp_matches(v.search_text, r.pattern)
)

select
    v.video_id,
    coalesce(m.topic, 'other') as topic
from videos v
left join matches m
    on v.video_id = m.video_id
   and m.row_num = 1
