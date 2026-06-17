with totals as (
    select
        count(*) as total_tracks,
        sum(case when liked then 1 else 0 end) as liked_tracks,
        count(distinct album_id) as albums,
        sum(duration_ms) / 3600000.0 as library_hours
    from {{ ref('yamusic_dim_tracks') }}
),

playlists as (
    select
        count(*) as playlists,
        sum(actual_track_count) as playlist_track_slots,
        sum(unique_track_count) as playlist_unique_tracks
    from {{ ref('yamusic_dim_playlists') }}
),

artists as (
    select
        count(*) as artists,
        max(track_count) as top_artist_track_count
    from {{ ref('yamusic_artist_affinity') }}
),

genres as (
    select
        count(*) filter (where genre != 'unknown') as known_genres,
        max(track_share) as top_genre_share
    from {{ ref('yamusic_genre_profile') }}
),

track_signals as (
    select
        sum(underrated_flag) as underrated_tracks,
        max(repeat_signal) as max_repeat_signal
    from {{ ref('yamusic_track_signals') }}
),

periods as (
    select
        count(*) as active_months,
        max(event_count) as busiest_month_events
    from {{ ref('yamusic_period_activity') }}
),

playlist_signals as (
    select
        sum(underrated_playlist_flag) as underrated_playlists
    from {{ ref('yamusic_playlist_signals') }}
),

freshness as (
    select
        max(ingested_at) as last_ingested_at,
        date_diff('hour', max(ingested_at), current_timestamp) as ingestion_age_hours
    from {{ ref('yamusic_fact_library_events') }}
),

manifest as (
    select *
    from {{ ref('stg_yamusic_manifest') }}
)

select
    manifest.manifest_source,
    manifest.manifest_generated_at,
    manifest.manifest_raw_dir,
    manifest.manifest_json_only,
    manifest.adapter_name,
    manifest.adapter_version,
    manifest.client_library,
    manifest.client_library_version,
    manifest.diagnostic_liked_shortcuts_seen,
    manifest.diagnostic_liked_tracks_written,
    manifest.diagnostic_liked_shortcuts_fetch_failed,
    manifest.diagnostic_liked_shortcuts_missing_track_id,
    manifest.diagnostic_liked_tracks_duplicate_skipped,
    manifest.diagnostic_liked_albums_seen,
    manifest.diagnostic_liked_albums_written,
    manifest.diagnostic_liked_albums_missing_id,
    manifest.diagnostic_liked_albums_duplicate_skipped,
    manifest.diagnostic_liked_artists_seen,
    manifest.diagnostic_liked_artists_written,
    manifest.diagnostic_liked_artists_missing_id,
    manifest.diagnostic_liked_artists_duplicate_skipped,
    manifest.diagnostic_liked_playlists_seen,
    manifest.diagnostic_liked_playlists_written,
    manifest.diagnostic_liked_playlists_missing_id,
    manifest.diagnostic_liked_playlists_duplicate_skipped,
    manifest.diagnostic_playlists_seen,
    manifest.diagnostic_playlists_written,
    manifest.diagnostic_playlists_missing_id,
    manifest.diagnostic_playlist_fetch_fallbacks,
    manifest.diagnostic_playlist_tracks_seen,
    manifest.diagnostic_playlist_tracks_written,
    manifest.diagnostic_playlist_tracks_fetch_failed,
    manifest.diagnostic_playlist_tracks_missing_track_id,
    manifest.diagnostic_playlist_tracks_duplicate_skipped,
    manifest.raw_tracks,
    manifest.raw_tracks_sha256,
    manifest.raw_artists,
    manifest.raw_artists_sha256,
    manifest.raw_albums,
    manifest.raw_albums_sha256,
    manifest.raw_playlists,
    manifest.raw_playlists_sha256,
    manifest.raw_playlist_tracks,
    manifest.raw_playlist_tracks_sha256,
    manifest.raw_user_library_events,
    manifest.raw_user_library_events_sha256,
    totals.total_tracks,
    coalesce(totals.liked_tracks, 0) as liked_tracks,
    totals.albums,
    artists.artists,
    playlists.playlists,
    coalesce(playlists.playlist_track_slots, 0) as playlist_track_slots,
    coalesce(playlists.playlist_unique_tracks, 0) as playlist_unique_tracks,
    coalesce(round(totals.library_hours, 2), 0) as library_hours,
    coalesce(round(artists.top_artist_track_count * 1.0 / nullif(totals.total_tracks, 0), 3), 0) as top_artist_concentration,
    genres.known_genres,
    coalesce(genres.top_genre_share, 0) as top_genre_share,
    coalesce(track_signals.underrated_tracks, 0) as underrated_tracks,
    coalesce(track_signals.max_repeat_signal, 0) as max_repeat_signal,
    periods.active_months,
    coalesce(periods.busiest_month_events, 0) as busiest_month_events,
    coalesce(playlist_signals.underrated_playlists, 0) as underrated_playlists,
    freshness.last_ingested_at,
    coalesce(freshness.ingestion_age_hours, 0) as ingestion_age_hours,
    case
        when freshness.last_ingested_at is null then 1
        when freshness.ingestion_age_hours > 168 then 1
        else 0
    end as stale_ingestion_flag,
    current_timestamp as calculated_at
from totals
cross join playlists
cross join artists
cross join genres
cross join track_signals
cross join periods
cross join playlist_signals
cross join freshness
cross join manifest
