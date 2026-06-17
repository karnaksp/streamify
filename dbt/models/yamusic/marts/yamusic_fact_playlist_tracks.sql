select
    playlist_id,
    track_id,
    position,
    source,
    ingested_at
from {{ ref('stg_yamusic_playlist_tracks') }}
