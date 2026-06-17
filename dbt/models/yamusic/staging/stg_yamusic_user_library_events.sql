select distinct
    cast(event_id as varchar) as event_id,
    cast(event_type as varchar) as event_type,
    cast(track_id as varchar) as track_id,
    cast(playlist_id as varchar) as playlist_id,
    cast(event_ts as timestamp) as event_ts,
    source,
    cast(ingested_at as timestamp) as ingested_at
from read_json(
    '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/user_library_events.jsonl',
    columns={
        event_id: 'VARCHAR',
        event_type: 'VARCHAR',
        track_id: 'VARCHAR',
        playlist_id: 'VARCHAR',
        event_ts: 'TIMESTAMP',
        source: 'VARCHAR',
        ingested_at: 'TIMESTAMP'
    }
)
where event_id is not null
