with source as (
    select *
    from read_json(
        '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/albums.jsonl',
        columns={
            album_id: 'VARCHAR',
            album_title: 'VARCHAR',
            genre: 'VARCHAR',
            release_year: 'INTEGER',
            source: 'VARCHAR',
            ingested_at: 'TIMESTAMP'
        }
    )
),

deduped as (
    select
        cast(album_id as varchar) as album_id,
        nullif(album_title, '') as album_title,
        nullif(genre, '') as genre,
        cast(release_year as integer) as release_year,
        source,
        cast(ingested_at as timestamp) as ingested_at,
        row_number() over (
            partition by cast(album_id as varchar)
            order by cast(ingested_at as timestamp) desc
        ) as row_num
    from source
    where album_id is not null
)

select * exclude (row_num)
from deduped
where row_num = 1
