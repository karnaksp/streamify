with source as (
    select *
    from read_json(
        '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/tracks.jsonl',
        columns={
            track_id: 'VARCHAR',
            title: 'VARCHAR',
            duration_ms: 'BIGINT',
            album_id: 'VARCHAR',
            album_title: 'VARCHAR',
            genre: 'VARCHAR',
            release_year: 'INTEGER',
            label: 'VARCHAR',
            artist_ids: 'VARCHAR[]',
            artist_names: 'VARCHAR[]',
            liked: 'BOOLEAN',
            source: 'VARCHAR',
            ingested_at: 'TIMESTAMP'
        }
    )
),

deduped as (
    select
        cast(track_id as varchar) as track_id,
        nullif(title, '') as title,
        cast(duration_ms as bigint) as duration_ms,
        cast(album_id as varchar) as album_id,
        album_title,
        nullif(genre, '') as genre,
        cast(release_year as integer) as release_year,
        nullif(label, '') as label,
        artist_ids,
        artist_names,
        coalesce(cast(liked as boolean), false) as liked,
        source,
        cast(ingested_at as timestamp) as ingested_at,
        row_number() over (
            partition by cast(track_id as varchar)
            order by cast(ingested_at as timestamp) desc
        ) as row_num
    from source
    where track_id is not null
)

select * exclude (row_num)
from deduped
where row_num = 1
