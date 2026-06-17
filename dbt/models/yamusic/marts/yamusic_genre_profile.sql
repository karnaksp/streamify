select
    coalesce(genre, 'unknown') as genre,
    count(*) as track_count,
    sum(case when liked then 1 else 0 end) as liked_track_count,
    round(sum(duration_ms) / 3600000.0, 2) as library_hours,
    round(count(*) * 1.0 / nullif(sum(count(*)) over (), 0), 3) as track_share
from {{ ref('yamusic_dim_tracks') }}
group by 1
