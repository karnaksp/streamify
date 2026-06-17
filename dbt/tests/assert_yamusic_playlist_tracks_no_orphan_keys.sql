select
    playlist_tracks.*
from {{ ref('yamusic_fact_playlist_tracks') }} as playlist_tracks
left join {{ ref('yamusic_dim_playlists') }} as playlists
    on playlist_tracks.playlist_id = playlists.playlist_id
left join {{ ref('yamusic_dim_tracks') }} as tracks
    on playlist_tracks.track_id = tracks.track_id
where playlists.playlist_id is null
   or tracks.track_id is null
