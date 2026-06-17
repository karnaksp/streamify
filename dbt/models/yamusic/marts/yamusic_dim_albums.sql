select
    album_id,
    album_title,
    genre,
    release_year,
    source,
    ingested_at
from {{ ref('stg_yamusic_albums') }}
