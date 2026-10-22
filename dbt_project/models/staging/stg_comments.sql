select
    comment_id,
    video_id,
    author_hash,
    trim(text) as text,
    like_count,
    published_at,
    updated_at,
    parent_id
from {{ source('bronze', 'comments') }}
where text is not null
  and length(trim(text)) > 0
qualify row_number() over (
    partition by comment_id
    order by updated_at desc nulls last
) = 1
