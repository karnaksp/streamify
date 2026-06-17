with events as (
    select
        date_trunc('month', event_ts) as activity_month,
        event_type,
        track_id
    from {{ ref('yamusic_fact_library_events') }}
    where event_ts is not null
),

event_tracks as (
    select
        events.activity_month,
        events.event_type,
        tracks.track_id,
        tracks.artist_names,
        tracks.genre
    from events
    left join {{ ref('yamusic_dim_tracks') }} as tracks using (track_id)
),

expanded_artists as (
    select
        activity_month,
        unnest(artist_names) as artist_name
    from event_tracks
    where artist_names is not null
),

event_summary as (
    select
        activity_month,
        count(distinct track_id) as active_tracks,
        count(*) as event_count,
        sum(case when event_type = 'liked_track' then 1 else 0 end) as liked_events,
        sum(case when event_type = 'playlist_membership' then 1 else 0 end) as playlist_events,
        count(distinct genre) filter (where genre is not null) as active_genres
    from event_tracks
    group by 1
),

artist_summary as (
    select
        activity_month,
        count(distinct artist_name) as active_artists
    from expanded_artists
    group by 1
)

select
    event_summary.activity_month,
    event_summary.active_tracks,
    event_summary.event_count,
    event_summary.liked_events,
    event_summary.playlist_events,
    coalesce(artist_summary.active_artists, 0) as active_artists,
    event_summary.active_genres
from event_summary
left join artist_summary using (activity_month)
