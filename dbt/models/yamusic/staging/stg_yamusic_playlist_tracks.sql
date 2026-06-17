select distinct
    cast(playlist_id as varchar) as playlist_id,
    cast(track_id as varchar) as track_id,
    cast(position as integer) as position,
    source,
    cast(ingested_at as timestamp) as ingested_at
from read_json(
    '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/playlist_tracks.jsonl',
    columns={
        playlist_id: 'VARCHAR',
        track_id: 'VARCHAR',
        position: 'INTEGER',
        added_at: 'TIMESTAMP',
        source: 'VARCHAR',
        ingested_at: 'TIMESTAMP'
    }
)
where playlist_id is not null
  and track_id is not null
