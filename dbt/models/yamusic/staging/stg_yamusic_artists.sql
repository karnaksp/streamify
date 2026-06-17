with source as (
    select *
    from read_json(
        '../{{ env_var("STREAMIFY_RAW_DIR", "data/raw/yamusic") }}/artists.jsonl',
        columns={
            artist_id: 'VARCHAR',
            artist_name: 'VARCHAR',
            source: 'VARCHAR',
            ingested_at: 'TIMESTAMP'
        }
    )
),

deduped as (
    select
        cast(artist_id as varchar) as artist_id,
        nullif(artist_name, '') as artist_name,
        source,
        cast(ingested_at as timestamp) as ingested_at,
        row_number() over (
            partition by cast(artist_id as varchar)
            order by cast(ingested_at as timestamp) desc
        ) as row_num
    from source
    where artist_id is not null
)

select * exclude (row_num)
from deduped
where row_num = 1
