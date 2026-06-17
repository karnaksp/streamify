with source as (
    select *
    from read_json(
        '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/playlists.jsonl',
        columns={
            playlist_id: 'VARCHAR',
            playlist_title: 'VARCHAR',
            track_count: 'INTEGER',
            source: 'VARCHAR',
            ingested_at: 'TIMESTAMP'
        }
    )
),

deduped as (
    select
        cast(playlist_id as varchar) as playlist_id,
        nullif(playlist_title, '') as playlist_title,
        cast(track_count as integer) as declared_track_count,
        source,
        cast(ingested_at as timestamp) as ingested_at,
        row_number() over (
            partition by cast(playlist_id as varchar)
            order by cast(ingested_at as timestamp) desc
        ) as row_num
    from source
    where playlist_id is not null
)

select * exclude (row_num)
from deduped
where row_num = 1
