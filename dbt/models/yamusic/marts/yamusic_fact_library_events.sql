select
    event_id,
    event_type,
    track_id,
    playlist_id,
    event_ts,
    source,
    ingested_at
from {{ ref('stg_yamusic_user_library_events') }}
