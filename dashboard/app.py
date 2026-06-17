from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv
from dashboard.actions import build_data_next_actions
from dashboard.filters import apply_track_filters

load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb"))
REPORT_PATH = Path(os.getenv("STREAMIFY_REPORT_PATH", "data/streamify_summary.md"))
SNAPSHOT_PATH = Path(os.getenv("STREAMIFY_SNAPSHOT_PATH", "data/streamify_snapshot.json"))
RECOMMENDATIONS_DIR = Path(os.getenv("STREAMIFY_RECOMMENDATIONS_DIR", "data/recommendations"))


def safe_int(value: object) -> int:
    return 0 if pd.isna(value) else int(value)


def safe_float(value: object) -> float:
    return 0.0 if pd.isna(value) else float(value)


def percent_label(value: object) -> str:
    return f"{safe_float(value) * 100:.1f}%"


def yes_no(value: object) -> str:
    return "yes" if safe_int(value) else "no"


@st.cache_data(ttl=30)
def query(sql: str) -> pd.DataFrame:
    with duckdb.connect(str(DB_PATH), read_only=True) as conn:
        return conn.execute(sql).fetchdf()


def require_database() -> bool:
    if DB_PATH.exists():
        return True
    st.error("Local DuckDB database is missing.")
    st.code("make ingest-sample\nmake dbt-build", language="bash")
    return False


st.set_page_config(page_title="Streamify Self-Analytics", page_icon="♪", layout="wide")

st.title("Streamify Self-Analytics")
st.caption("Local Yandex Music metadata analytics. Audio is not downloaded or stored.")

if not require_database():
    st.stop()

try:
    profile = query("select * from yamusic_library_profile")
except Exception as exc:
    st.error("The local marts are not ready yet. Run ingestion and dbt build first.")
    st.code("make ingest-sample\nmake dbt-build", language="bash")
    st.exception(exc)
    st.stop()

if profile.empty:
    st.warning("No library data is available yet.")
    st.stop()

row = profile.iloc[0]
has_library_data = safe_int(row["total_tracks"]) > 0
metric_cols = st.columns(5)
metric_cols[0].metric("Tracks", safe_int(row["total_tracks"]))
metric_cols[1].metric("Liked", safe_int(row["liked_tracks"]))
metric_cols[2].metric("Artists", safe_int(row["artists"]))
metric_cols[3].metric("Playlists", safe_int(row["playlists"]))
metric_cols[4].metric("Hours", safe_float(row["library_hours"]))

source_cols = st.columns(3)
source_cols[0].metric("Source", str(row["manifest_source"]))
source_cols[1].metric("Raw tracks", safe_int(row["raw_tracks"]))
source_cols[2].metric(
    "Manifest generated",
    "missing" if pd.isna(row["manifest_generated_at"]) else str(row["manifest_generated_at"])[:19],
)
st.caption(
    f"Ingestion adapter: {row['adapter_name']} {row['adapter_version']} "
    f"using {row['client_library']} {'' if pd.isna(row['client_library_version']) else row['client_library_version']}"
)

signal_cols = st.columns(5)
signal_cols[0].metric("Known genres", safe_int(row["known_genres"]))
signal_cols[1].metric("Active months", safe_int(row["active_months"]))
signal_cols[2].metric("Underrated tracks", safe_int(row["underrated_tracks"]))
signal_cols[3].metric("Underrated playlists", safe_int(row["underrated_playlists"]))
signal_cols[4].metric("Top artist concentration", percent_label(row["top_artist_concentration"]))

if not has_library_data:
    st.warning("No Yandex Music library metadata was returned for this run.")
    st.code("make ingest\nmake dbt-build", language="bash")

genre_options = query(
    """
    select distinct coalesce(genre, 'unknown') as genre
    from yamusic_dim_tracks
    order by genre
    """
)["genre"].tolist()

st.sidebar.header("Filters")
selected_genres = st.sidebar.multiselect("Genres", genre_options, default=genre_options)
liked_mode = st.sidebar.selectbox("Liked", ["All", "Liked", "Not liked"])
track_search = st.sidebar.text_input("Search").strip().lower()

tab_overview, tab_periods, tab_artists, tab_genres, tab_playlists, tab_tracks, tab_actions, tab_quality = st.tabs(
    ["Overview", "Periods", "Artists", "Genres", "Playlists", "Tracks", "Actions", "Data Quality"]
)

with tab_overview:
    tracks = query(
        """
        select title, artist_display, album_title, genre, liked, duration_seconds
        from yamusic_dim_tracks
        order by liked desc, title
        limit 5000
        """
    )
    tracks = apply_track_filters(tracks, selected_genres, liked_mode, track_search)
    st.subheader("Library snapshot")
    st.metric("Filtered tracks", len(tracks.index))
    st.dataframe(tracks, use_container_width=True, hide_index=True)

with tab_periods:
    periods = query(
        """
        select activity_month, event_count, liked_events, playlist_events, active_tracks, active_artists, active_genres
        from yamusic_period_activity
        order by activity_month
        """
    )
    st.subheader("Activity periods")
    if not periods.empty:
        chart_data = periods.set_index("activity_month")[["event_count", "active_tracks", "active_artists"]]
        st.line_chart(chart_data)
    st.dataframe(periods, use_container_width=True, hide_index=True)
    genre_periods = query(
        """
        select activity_month, genre, event_count, active_tracks, event_share_in_month
        from yamusic_genre_periods
        order by activity_month, event_share_in_month desc, genre
        """
    )
    st.subheader("Genre shifts")
    if not genre_periods.empty:
        genre_shift_chart = genre_periods.pivot(
            index="activity_month", columns="genre", values="event_share_in_month"
        ).fillna(0)
        st.line_chart(genre_shift_chart)
        genre_periods["event_share_in_month"] = genre_periods["event_share_in_month"].map(lambda value: f"{value * 100:.1f}%")
    st.dataframe(genre_periods, use_container_width=True, hide_index=True)

with tab_artists:
    artists = query(
        """
        select artist_name, track_count, liked_track_count, playlist_appearances
        from yamusic_artist_affinity
        order by track_count desc, playlist_appearances desc, artist_name
        limit 30
        """
    )
    st.subheader("Artist affinity")
    if not artists.empty:
        top_artist = artists.iloc[0]
        st.caption(
            f"Top artist: {top_artist['artist_name']} with {safe_int(top_artist['track_count'])} tracks "
            f"and {safe_int(top_artist['liked_track_count'])} liked tracks."
        )
        st.bar_chart(artists.set_index("artist_name")["track_count"])
    st.dataframe(artists, use_container_width=True, hide_index=True)

with tab_genres:
    genres = query(
        """
        select genre, track_count, liked_track_count, library_hours, track_share
        from yamusic_genre_profile
        order by track_count desc, genre
        """
    )
    st.subheader("Genre diversity")
    if not genres.empty:
        st.bar_chart(genres.set_index("genre")["track_count"])
        genres["track_share"] = genres["track_share"].map(lambda value: f"{value * 100:.1f}%")
    st.dataframe(genres, use_container_width=True, hide_index=True)
    genre_periods = query(
        """
        select activity_month, genre, event_share_in_month, event_count, active_tracks
        from yamusic_genre_periods
        order by activity_month desc, event_share_in_month desc, genre
        """
    )
    st.subheader("Genre shifts by month")
    if not genre_periods.empty:
        genre_periods["event_share_in_month"] = genre_periods["event_share_in_month"].map(lambda value: f"{value * 100:.1f}%")
    st.dataframe(genre_periods, use_container_width=True, hide_index=True)

with tab_playlists:
    playlists = query(
        """
        select playlist_title, actual_track_count, unique_track_count, declared_track_count
        from yamusic_dim_playlists
        order by actual_track_count desc, playlist_title
        """
    )
    st.subheader("Playlist coverage")
    st.dataframe(playlists, use_container_width=True, hide_index=True)
    playlist_signals = query(
        """
        select playlist_title, uniqueness_ratio, max_overlap, overlapped_track_mentions, underrated_playlist_flag
        from yamusic_playlist_signals
        order by underrated_playlist_flag desc, uniqueness_ratio desc, playlist_title
        """
    )
    st.subheader("Underrated playlist signals")
    if not playlist_signals.empty:
        playlist_signals["uniqueness_ratio"] = playlist_signals["uniqueness_ratio"].map(lambda value: f"{value * 100:.1f}%")
        playlist_signals["max_overlap"] = playlist_signals["max_overlap"].map(lambda value: f"{value * 100:.1f}%")
        playlist_signals["underrated_playlist_flag"] = playlist_signals["underrated_playlist_flag"].map(lambda value: "yes" if value else "no")
    st.dataframe(playlist_signals, use_container_width=True, hide_index=True)
    overlap = query(
        """
        select playlist_a_title, playlist_b_title, overlap_track_count, jaccard_overlap
        from yamusic_playlist_overlap
        order by overlap_track_count desc, jaccard_overlap desc
        limit 50
        """
    )
    st.subheader("Playlist overlap")
    if not overlap.empty:
        overlap["jaccard_overlap"] = overlap["jaccard_overlap"].map(lambda value: f"{value * 100:.1f}%")
    st.dataframe(overlap, use_container_width=True, hide_index=True)

with tab_tracks:
    track_signals = query(
        """
        select
            title,
            artist_display,
            genre,
            liked,
            playlist_count,
            event_count,
            repeat_signal,
            underrated_flag,
            first_event_ts,
            last_event_ts
        from yamusic_track_signals
        order by underrated_flag desc, repeat_signal desc, title
        limit 5000
        """
    )
    track_signals = apply_track_filters(track_signals, selected_genres, liked_mode, track_search)
    st.subheader("Repeated and underrated tracks")
    st.metric("Filtered track signals", len(track_signals.index))
    if not track_signals.empty:
        top_repeat = track_signals.sort_values(["repeat_signal", "playlist_count"], ascending=False).iloc[0]
        st.caption(
            f"Highest repeat signal: {top_repeat['title']} by {top_repeat['artist_display']} "
            f"with score {safe_int(top_repeat['repeat_signal'])}."
        )
        track_signals["liked"] = track_signals["liked"].map(lambda value: "yes" if value else "no")
        track_signals["underrated_flag"] = track_signals["underrated_flag"].map(lambda value: "yes" if value else "no")
    st.dataframe(track_signals, use_container_width=True, hide_index=True)

with tab_actions:
    st.subheader("Next actions")
    action_profile = row.to_dict()
    for action in build_data_next_actions(action_profile):
        st.write(f"- {action}")

    rediscovery = query(
        """
        select title, artist_display, genre, playlist_slots, playlist_count
        from yamusic_track_signals
        where underrated_flag = true
        order by playlist_slots asc, playlist_count asc, title
        limit 25
        """
    )
    st.subheader("Rediscovery queue")
    st.dataframe(rediscovery, use_container_width=True, hide_index=True)

    cleanup = query(
        """
        select playlist_a_title, playlist_b_title, overlap_track_count, jaccard_overlap
        from yamusic_playlist_overlap
        order by jaccard_overlap desc, overlap_track_count desc, playlist_a_title, playlist_b_title
        limit 25
        """
    )
    if not cleanup.empty:
        cleanup["jaccard_overlap"] = cleanup["jaccard_overlap"].map(lambda value: f"{value * 100:.1f}%")
    st.subheader("Playlist cleanup candidates")
    st.dataframe(cleanup, use_container_width=True, hide_index=True)

    standout_playlists = query(
        """
        select playlist_title, actual_track_count, unique_track_count, uniqueness_ratio, max_overlap
        from yamusic_playlist_signals
        where underrated_playlist_flag = true
        order by uniqueness_ratio desc, actual_track_count desc, playlist_title
        limit 25
        """
    )
    if not standout_playlists.empty:
        standout_playlists["uniqueness_ratio"] = standout_playlists["uniqueness_ratio"].map(lambda value: f"{value * 100:.1f}%")
        standout_playlists["max_overlap"] = standout_playlists["max_overlap"].map(lambda value: f"{value * 100:.1f}%")
    st.subheader("Standout playlists")
    st.dataframe(standout_playlists, use_container_width=True, hide_index=True)

    export_cols = st.columns(2)
    if REPORT_PATH.exists():
        export_cols[0].download_button(
            "Download summary",
            data=REPORT_PATH.read_text(encoding="utf-8"),
            file_name=REPORT_PATH.name,
            mime="text/markdown",
        )
    if SNAPSHOT_PATH.exists():
        export_cols[1].download_button(
            "Download snapshot",
            data=SNAPSHOT_PATH.read_text(encoding="utf-8"),
            file_name=SNAPSHOT_PATH.name,
            mime="application/json",
        )
    recommendation_files = sorted(RECOMMENDATIONS_DIR.glob("*.csv")) if RECOMMENDATIONS_DIR.exists() else []
    if recommendation_files:
        st.subheader("Download action queues")
        for path in recommendation_files:
            st.download_button(
                path.stem.replace("_", " ").title(),
                data=path.read_text(encoding="utf-8"),
                file_name=path.name,
                mime="text/csv",
            )

with tab_quality:
    quality = {
        "database": str(DB_PATH),
        "manifest_source": str(row["manifest_source"]),
        "manifest_generated_at": None if pd.isna(row["manifest_generated_at"]) else str(row["manifest_generated_at"]),
        "manifest_raw_dir": str(row["manifest_raw_dir"]),
        "manifest_json_only": bool(row["manifest_json_only"]),
        "adapter": {
            "adapter_name": str(row["adapter_name"]),
            "adapter_version": str(row["adapter_version"]),
            "client_library": str(row["client_library"]),
            "client_library_version": None if pd.isna(row["client_library_version"]) else str(row["client_library_version"]),
        },
        "ingestion_diagnostics": {
            "liked_shortcuts_seen": safe_int(row["diagnostic_liked_shortcuts_seen"]),
            "liked_tracks_written": safe_int(row["diagnostic_liked_tracks_written"]),
            "liked_shortcuts_fetch_failed": safe_int(row["diagnostic_liked_shortcuts_fetch_failed"]),
            "liked_shortcuts_missing_track_id": safe_int(row["diagnostic_liked_shortcuts_missing_track_id"]),
            "liked_tracks_duplicate_skipped": safe_int(row["diagnostic_liked_tracks_duplicate_skipped"]),
            "liked_albums_seen": safe_int(row["diagnostic_liked_albums_seen"]),
            "liked_albums_written": safe_int(row["diagnostic_liked_albums_written"]),
            "liked_albums_missing_id": safe_int(row["diagnostic_liked_albums_missing_id"]),
            "liked_albums_duplicate_skipped": safe_int(row["diagnostic_liked_albums_duplicate_skipped"]),
            "liked_artists_seen": safe_int(row["diagnostic_liked_artists_seen"]),
            "liked_artists_written": safe_int(row["diagnostic_liked_artists_written"]),
            "liked_artists_missing_id": safe_int(row["diagnostic_liked_artists_missing_id"]),
            "liked_artists_duplicate_skipped": safe_int(row["diagnostic_liked_artists_duplicate_skipped"]),
            "liked_playlists_seen": safe_int(row["diagnostic_liked_playlists_seen"]),
            "liked_playlists_written": safe_int(row["diagnostic_liked_playlists_written"]),
            "liked_playlists_missing_id": safe_int(row["diagnostic_liked_playlists_missing_id"]),
            "liked_playlists_duplicate_skipped": safe_int(row["diagnostic_liked_playlists_duplicate_skipped"]),
            "playlists_seen": safe_int(row["diagnostic_playlists_seen"]),
            "playlists_written": safe_int(row["diagnostic_playlists_written"]),
            "playlists_missing_id": safe_int(row["diagnostic_playlists_missing_id"]),
            "playlist_fetch_fallbacks": safe_int(row["diagnostic_playlist_fetch_fallbacks"]),
            "playlist_tracks_seen": safe_int(row["diagnostic_playlist_tracks_seen"]),
            "playlist_tracks_written": safe_int(row["diagnostic_playlist_tracks_written"]),
            "playlist_tracks_fetch_failed": safe_int(row["diagnostic_playlist_tracks_fetch_failed"]),
            "playlist_tracks_missing_track_id": safe_int(row["diagnostic_playlist_tracks_missing_track_id"]),
            "playlist_tracks_duplicate_skipped": safe_int(row["diagnostic_playlist_tracks_duplicate_skipped"]),
        },
        "raw_counts": {
            "tracks": safe_int(row["raw_tracks"]),
            "artists": safe_int(row["raw_artists"]),
            "albums": safe_int(row["raw_albums"]),
            "playlists": safe_int(row["raw_playlists"]),
            "playlist_tracks": safe_int(row["raw_playlist_tracks"]),
            "user_library_events": safe_int(row["raw_user_library_events"]),
        },
        "raw_checksums": {
            "tracks": str(row["raw_tracks_sha256"]),
            "artists": str(row["raw_artists_sha256"]),
            "albums": str(row["raw_albums_sha256"]),
            "playlists": str(row["raw_playlists_sha256"]),
            "playlist_tracks": str(row["raw_playlist_tracks_sha256"]),
            "user_library_events": str(row["raw_user_library_events_sha256"]),
        },
        "calculated_at": str(row["calculated_at"]),
        "top_artist_concentration": percent_label(row["top_artist_concentration"]),
        "top_genre_share": percent_label(row["top_genre_share"]),
        "playlist_track_slots": safe_int(row["playlist_track_slots"]),
        "playlist_unique_tracks": safe_int(row["playlist_unique_tracks"]),
        "busiest_month_events": safe_int(row["busiest_month_events"]),
        "max_repeat_signal": safe_int(row["max_repeat_signal"]),
        "last_ingested_at": None if pd.isna(row["last_ingested_at"]) else str(row["last_ingested_at"]),
        "ingestion_age_hours": safe_int(row["ingestion_age_hours"]),
        "stale_ingestion_flag": yes_no(row["stale_ingestion_flag"]),
    }
    st.subheader("Local data quality signals")
    st.json(quality)
    st.info("Run `make test` for schema, relationship, compile and compose checks.")
