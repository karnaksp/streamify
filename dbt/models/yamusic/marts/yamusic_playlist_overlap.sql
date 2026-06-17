with pairs as (
    select
        left_tracks.playlist_id as playlist_a_id,
        right_tracks.playlist_id as playlist_b_id,
        count(*) as overlap_track_count
    from {{ ref('yamusic_fact_playlist_tracks') }} as left_tracks
    join {{ ref('yamusic_fact_playlist_tracks') }} as right_tracks
        on left_tracks.track_id = right_tracks.track_id
       and left_tracks.playlist_id < right_tracks.playlist_id
    group by 1, 2
),

playlist_sizes as (
    select
        playlist_id,
        count(distinct track_id) as track_count
    from {{ ref('yamusic_fact_playlist_tracks') }}
    group by 1
)

select
    pairs.playlist_a_id,
    playlist_a.playlist_title as playlist_a_title,
    pairs.playlist_b_id,
    playlist_b.playlist_title as playlist_b_title,
    pairs.overlap_track_count,
    round(
        pairs.overlap_track_count * 1.0
        / nullif(size_a.track_count + size_b.track_count - pairs.overlap_track_count, 0),
        3
    ) as jaccard_overlap
from pairs
left join {{ ref('yamusic_dim_playlists') }} as playlist_a
    on pairs.playlist_a_id = playlist_a.playlist_id
left join {{ ref('yamusic_dim_playlists') }} as playlist_b
    on pairs.playlist_b_id = playlist_b.playlist_id
left join playlist_sizes as size_a
    on pairs.playlist_a_id = size_a.playlist_id
left join playlist_sizes as size_b
    on pairs.playlist_b_id = size_b.playlist_id
