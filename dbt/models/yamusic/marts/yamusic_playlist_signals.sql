with overlap as (
    select
        playlist_a_id as playlist_id,
        max(jaccard_overlap) as max_overlap,
        sum(overlap_track_count) as overlapped_track_mentions
    from {{ ref('yamusic_playlist_overlap') }}
    group by 1

    union all

    select
        playlist_b_id as playlist_id,
        max(jaccard_overlap) as max_overlap,
        sum(overlap_track_count) as overlapped_track_mentions
    from {{ ref('yamusic_playlist_overlap') }}
    group by 1
),

overlap_by_playlist as (
    select
        playlist_id,
        max(max_overlap) as max_overlap,
        sum(overlapped_track_mentions) as overlapped_track_mentions
    from overlap
    group by 1
)

select
    playlists.playlist_id,
    playlists.playlist_title,
    playlists.actual_track_count,
    playlists.unique_track_count,
    round(playlists.unique_track_count * 1.0 / nullif(playlists.actual_track_count, 0), 3) as uniqueness_ratio,
    coalesce(overlap_by_playlist.max_overlap, 0) as max_overlap,
    coalesce(overlap_by_playlist.overlapped_track_mentions, 0) as overlapped_track_mentions,
    case
        when playlists.unique_track_count >= 2
         and coalesce(overlap_by_playlist.max_overlap, 0) <= 0.25 then 1
        else 0
    end as underrated_playlist_flag
from {{ ref('yamusic_dim_playlists') }} as playlists
left join overlap_by_playlist using (playlist_id)
