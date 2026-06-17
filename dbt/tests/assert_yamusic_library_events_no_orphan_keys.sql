select
    events.*
from {{ ref('yamusic_fact_library_events') }} as events
left join {{ ref('yamusic_dim_tracks') }} as tracks
    on events.track_id = tracks.track_id
left join {{ ref('yamusic_dim_playlists') }} as playlists
    on events.playlist_id = playlists.playlist_id
where tracks.track_id is null
   or (
        events.playlist_id is not null
        and playlists.playlist_id is null
   )
