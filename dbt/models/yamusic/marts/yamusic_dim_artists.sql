select
    artist_id,
    artist_name,
    source,
    ingested_at
from {{ ref('stg_yamusic_artists') }}
