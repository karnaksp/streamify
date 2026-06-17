select
    track_id,
    title,
    duration_ms,
    round(duration_ms / 1000.0, 1) as duration_seconds,
    album_id,
    album_title,
    genre,
    release_year,
    label,
    artist_names,
    array_to_string(artist_names, ', ') as artist_display,
    liked,
    source,
    ingested_at
from {{ ref('stg_yamusic_tracks') }}
