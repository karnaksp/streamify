with actual_counts as (
    select
        playlist_id,
        count(*) as actual_track_count,
        count(distinct track_id) as unique_track_count
    from {{ ref('stg_yamusic_playlist_tracks') }}
    group by 1
)

select
    playlists.playlist_id,
    playlists.playlist_title,
    playlists.declared_track_count,
    coalesce(actual_counts.actual_track_count, 0) as actual_track_count,
    coalesce(actual_counts.unique_track_count, 0) as unique_track_count,
    playlists.source,
    playlists.ingested_at
from {{ ref('stg_yamusic_playlists') }} as playlists
left join actual_counts using (playlist_id)
