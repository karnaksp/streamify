with event_tracks as (
    select
        date_trunc('month', events.event_ts)::date as activity_month,
        coalesce(tracks.genre, 'unknown') as genre,
        events.event_type,
        events.track_id
    from {{ ref('yamusic_fact_library_events') }} as events
    left join {{ ref('yamusic_dim_tracks') }} as tracks
        on events.track_id = tracks.track_id
    where events.event_ts is not null
),

monthly_genres as (
    select
        activity_month,
        genre,
        count(*) as event_count,
        count(distinct track_id) as active_tracks,
        sum(case when event_type = 'liked_track' then 1 else 0 end) as liked_events,
        sum(case when event_type = 'playlist_membership' then 1 else 0 end) as playlist_events
    from event_tracks
    group by 1, 2
)

select
    activity_month,
    genre,
    event_count,
    active_tracks,
    liked_events,
    playlist_events,
    round(event_count * 1.0 / nullif(sum(event_count) over (partition by activity_month), 0), 3) as event_share_in_month
from monthly_genres
