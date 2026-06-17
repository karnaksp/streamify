with playlist_presence as (
    select
        track_id,
        count(*) as playlist_slots,
        count(distinct playlist_id) as playlist_count
    from {{ ref('yamusic_fact_playlist_tracks') }}
    group by 1
),

events as (
    select
        track_id,
        count(*) as event_count,
        min(event_ts) as first_event_ts,
        max(event_ts) as last_event_ts
    from {{ ref('yamusic_fact_library_events') }}
    where track_id is not null
    group by 1
)

select
    tracks.track_id,
    tracks.title,
    tracks.artist_display,
    tracks.album_title,
    tracks.genre,
    tracks.release_year,
    tracks.liked,
    coalesce(playlist_presence.playlist_slots, 0) as playlist_slots,
    coalesce(playlist_presence.playlist_count, 0) as playlist_count,
    coalesce(events.event_count, 0) as event_count,
    events.first_event_ts,
    events.last_event_ts,
    coalesce(playlist_presence.playlist_slots, 0) + coalesce(events.event_count, 0) as repeat_signal,
    case
        when tracks.liked and coalesce(playlist_presence.playlist_count, 0) <= 1 then 1
        else 0
    end as underrated_flag
from {{ ref('yamusic_dim_tracks') }} as tracks
left join playlist_presence using (track_id)
left join events using (track_id)
