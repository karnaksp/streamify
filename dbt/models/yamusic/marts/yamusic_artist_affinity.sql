with track_artist as (
    select
        tracks.track_id,
        tracks.title,
        tracks.liked,
        unnest(tracks.artist_names) as artist_name
    from {{ ref('yamusic_dim_tracks') }} as tracks
),

playlist_presence as (
    select
        track_id,
        count(distinct playlist_id) as playlist_count
    from {{ ref('yamusic_fact_playlist_tracks') }}
    group by 1
)

select
    artist_name,
    count(distinct track_artist.track_id) as track_count,
    sum(case when liked then 1 else 0 end) as liked_track_count,
    coalesce(sum(playlist_presence.playlist_count), 0) as playlist_appearances,
    round(avg(coalesce(playlist_presence.playlist_count, 0)), 2) as avg_playlist_appearances_per_track
from track_artist
left join playlist_presence using (track_id)
where artist_name is not null and artist_name != ''
group by 1
