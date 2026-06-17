from __future__ import annotations

import html
import math
import os
import sys
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dashboard.actions import build_data_next_actions
from dashboard.filters import apply_track_filters
from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DB_PATH = Path(os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb"))
REPORT_PATH = Path(os.getenv("STREAMIFY_REPORT_PATH", "data/streamify_summary.md"))
SNAPSHOT_PATH = Path(os.getenv("STREAMIFY_SNAPSHOT_PATH", "data/streamify_snapshot.json"))
RECOMMENDATIONS_DIR = Path(os.getenv("STREAMIFY_RECOMMENDATIONS_DIR", "data/recommendations"))
ENRICHMENT_DIR = Path(os.getenv("STREAMIFY_ENRICHMENT_DIR", "data/enrichment"))


def safe_int(value: object) -> int:
    return 0 if pd.isna(value) else int(value)


def safe_float(value: object) -> float:
    return 0.0 if pd.isna(value) else float(value)


def compact_int(value: object) -> str:
    number = safe_int(value)
    return f"{number:,}".replace(",", " ")


def percent_label(value: object) -> str:
    return f"{safe_float(value) * 100:.1f}%"


def pct_from_whole(part: object, whole: object) -> str:
    denominator = safe_float(whole)
    if denominator == 0:
        return "0.0%"
    return f"{safe_float(part) * 100 / denominator:.1f}%"


def yes_no(value: object) -> str:
    return "yes" if safe_int(value) else "no"


def escape(value: object) -> str:
    if pd.isna(value):
        return ""
    return html.escape(str(value))


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


def first_record(frame: pd.DataFrame) -> dict[str, object]:
    return {} if frame.empty else frame.iloc[0].to_dict()


def optional_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def style_app() -> None:
    st.markdown(
        """
        <style>
        :root {
          --sf-ink: #17201f;
          --sf-muted: #66736f;
          --sf-line: #dfe6e1;
          --sf-panel: #f7faf7;
          --sf-teal: #0f766e;
          --sf-coral: #c2412d;
          --sf-gold: #a16207;
          --sf-blue: #2563eb;
        }
        .stApp { background: #fbfcfa; color: var(--sf-ink); }
        .block-container { padding-top: 1.4rem; max-width: 1440px; }
        h1, h2, h3 { letter-spacing: 0; }
        section[data-testid="stSidebar"] {
          background: #24242d;
          border-right: 1px solid #343640;
        }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {
          color: #f4f7f4;
        }
        section[data-testid="stSidebar"] div[data-testid="stMetric"] {
          background: #ffffff;
        }
        section[data-testid="stSidebar"] div[data-testid="stMetric"] * {
          color: var(--sf-ink) !important;
        }
        div[data-testid="stMetric"] {
          background: #ffffff;
          border: 1px solid var(--sf-line);
          border-left: 4px solid var(--sf-teal);
          border-radius: 8px;
          padding: 12px 14px;
          box-shadow: 0 1px 2px rgba(23, 32, 31, 0.04);
        }
        div[data-testid="stMetric"] label { color: var(--sf-muted); }
        div[data-testid="stMetric"] [data-testid="stMetricValue"] {
          color: var(--sf-ink);
          font-size: 1.65rem;
        }
        .sf-hero {
          border: 1px solid #ccd8d1;
          border-radius: 8px;
          padding: 22px 24px;
          background:
            linear-gradient(120deg, rgba(15, 118, 110, 0.12), rgba(162, 98, 7, 0.08)),
            #f7faf7;
          margin-bottom: 18px;
        }
        .sf-kicker {
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
          color: var(--sf-teal);
          margin-bottom: 4px;
        }
        .sf-hero h1 { margin: 0 0 6px; font-size: 2.05rem; }
        .sf-hero p { color: #43504c; margin: 0; max-width: 920px; }
        .sf-card-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
          gap: 12px;
          margin: 14px 0 8px;
        }
        .sf-insight {
          background: #ffffff;
          border: 1px solid var(--sf-line);
          border-top: 4px solid var(--accent);
          border-radius: 8px;
          padding: 14px 15px;
          min-height: 126px;
        }
        .sf-insight .label {
          color: var(--sf-muted);
          font-size: 0.78rem;
          font-weight: 700;
          text-transform: uppercase;
          margin-bottom: 6px;
        }
        .sf-insight .value {
          color: var(--sf-ink);
          font-size: 1.35rem;
          font-weight: 800;
          line-height: 1.15;
          margin-bottom: 8px;
        }
        .sf-insight .note {
          color: #4b5a55;
          font-size: 0.92rem;
          line-height: 1.35;
        }
        .sf-section-note {
          color: var(--sf-muted);
          font-size: 0.92rem;
          margin: -0.45rem 0 0.75rem;
        }
        .sf-pill {
          display: inline-block;
          border: 1px solid var(--sf-line);
          border-radius: 999px;
          padding: 4px 9px;
          margin: 0 5px 6px 0;
          background: #fff;
          color: #3d4945;
          font-size: 0.82rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def insight_card(label: str, value: object, note: str, accent: str) -> None:
    st.markdown(
        f"""
        <div class="sf-insight" style="--accent:{accent};">
          <div class="label">{escape(label)}</div>
          <div class="value">{escape(value)}</div>
          <div class="note">{escape(note)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_percent_column(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    result = frame.copy()
    if column in result.columns:
        result[column] = result[column].map(lambda value: f"{safe_float(value) * 100:.1f}%")
    return result


def apply_focus_filters(
    frame: pd.DataFrame,
    selected_genres: list[str],
    liked_mode: str,
    search: str,
    year_range: tuple[int, int],
    min_repeat: int,
    max_playlist_count: int | None,
) -> pd.DataFrame:
    filtered = apply_track_filters(frame, selected_genres, liked_mode, search)
    if "release_year" in filtered.columns:
        filtered = filtered[
            filtered["release_year"].isna()
            | filtered["release_year"].between(year_range[0], year_range[1])
        ]
    if "repeat_signal" in filtered.columns and min_repeat > 0:
        filtered = filtered[filtered["repeat_signal"] >= min_repeat]
    if max_playlist_count is not None and "playlist_count" in filtered.columns:
        filtered = filtered[filtered["playlist_count"] <= max_playlist_count]
    return filtered


def render_track_cards(frame: pd.DataFrame, limit: int = 8) -> None:
    if frame.empty:
        st.info("No tracks match the current focus.")
        return
    rows = frame.head(limit).to_dict("records")
    for start in range(0, len(rows), 2):
        cols = st.columns(2)
        for col, item in zip(cols, rows[start : start + 2]):
            with col:
                playlist_note = f"{safe_int(item.get('playlist_count'))} playlists"
                repeat_note = f"repeat {safe_int(item.get('repeat_signal'))}"
                genre_note = item.get("genre") or "unknown genre"
                insight_card(
                    item.get("title", "unknown track"),
                    item.get("artist_display", "unknown artist"),
                    f"{genre_note} · {playlist_note} · {repeat_note}",
                    "#0f766e" if safe_int(item.get("playlist_count")) == 0 else "#2563eb",
                )


def polish_chart(chart: alt.Chart) -> alt.Chart:
    return (
        chart.configure(background="#ffffff")
        .configure_view(fill="#ffffff", stroke="#dfe6e1")
        .configure_axis(
            labelColor="#43504c",
            titleColor="#17201f",
            gridColor="#e6ece8",
            domainColor="#cfd8d2",
            tickColor="#cfd8d2",
        )
        .configure_legend(labelColor="#17201f", titleColor="#17201f")
        .configure_title(color="#17201f", anchor="start")
    )


def hbar_chart(frame: pd.DataFrame, x: str, y: str, title: str, color: str = "#0f766e") -> None:
    if frame.empty:
        st.info("No data for this chart.")
        return
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=3, color=color)
        .encode(
            x=alt.X(f"{x}:Q", title=None),
            y=alt.Y(f"{y}:N", sort="-x", title=None),
            tooltip=list(frame.columns),
        )
        .properties(title=title, height=max(260, min(520, len(frame.index) * 30)))
    )
    st.altair_chart(polish_chart(chart), use_container_width=True, theme=None)


def playlist_subway_frames(overlap: pd.DataFrame, limit: int = 14) -> tuple[pd.DataFrame, pd.DataFrame]:
    if overlap.empty:
        return pd.DataFrame(), pd.DataFrame()

    edges = overlap.head(40).copy()
    playlist_names = pd.concat([edges["playlist_a_title"], edges["playlist_b_title"]], ignore_index=True)
    node_stats = (
        playlist_names.value_counts()
        .rename_axis("playlist_title")
        .reset_index(name="connection_count")
        .head(limit)
    )
    selected = set(node_stats["playlist_title"])
    edges = edges[
        edges["playlist_a_title"].isin(selected)
        & edges["playlist_b_title"].isin(selected)
    ].copy()
    if edges.empty:
        return pd.DataFrame(), pd.DataFrame()

    overlap_mentions = pd.concat(
        [
            edges[["playlist_a_title", "jaccard_overlap", "overlap_track_count"]].rename(
                columns={"playlist_a_title": "playlist_title"}
            ),
            edges[["playlist_b_title", "jaccard_overlap", "overlap_track_count"]].rename(
                columns={"playlist_b_title": "playlist_title"}
            ),
        ],
        ignore_index=True,
    )
    node_stats = node_stats.merge(
        overlap_mentions.groupby("playlist_title", as_index=False).agg(
            max_jaccard=("jaccard_overlap", "max"),
            overlap_tracks=("overlap_track_count", "sum"),
        ),
        on="playlist_title",
        how="left",
    )

    lane_count = min(4, max(1, math.ceil(len(node_stats.index) / 4)))
    node_stats["x"] = node_stats.index // lane_count
    node_stats["y"] = node_stats.index % lane_count
    node_lookup = node_stats.set_index("playlist_title")[["x", "y"]]

    edges = edges.merge(node_lookup, left_on="playlist_a_title", right_index=True)
    edges = edges.merge(node_lookup, left_on="playlist_b_title", right_index=True, suffixes=("_a", "_b"))
    edges["pair"] = edges["playlist_a_title"] + " / " + edges["playlist_b_title"]
    return node_stats, edges


def source_payload(row: pd.Series) -> dict[str, object]:
    return {
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


st.set_page_config(
    page_title="Streamify Self-Analytics",
    page_icon="S",
    layout="wide",
    initial_sidebar_state="expanded",
)
style_app()

st.markdown(
    """
    <div class="sf-hero">
      <div class="sf-kicker">Local Yandex Music self-analytics</div>
      <h1>Streamify Taste Console</h1>
      <p>Personal metadata lakehouse for taste, rediscovery, playlist quality and data health. Audio is not downloaded or stored.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

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

top_artists = query(
    """
    select artist_name, track_count, liked_track_count, playlist_appearances
    from yamusic_artist_affinity
    order by track_count desc, playlist_appearances desc, artist_name
    limit 25
    """
)
top_genres = query(
    """
    select genre, track_count, liked_track_count, library_hours, track_share
    from yamusic_genre_profile
    order by track_count desc, genre
    limit 20
    """
)
periods = query(
    """
    select activity_month, event_count, liked_events, playlist_events, active_tracks, active_artists, active_genres
    from yamusic_period_activity
    order by activity_month
    """
)
track_signals_all = query(
    """
    select
        title,
        artist_display,
        album_title,
        genre,
        release_year,
        liked,
        playlist_slots,
        playlist_count,
        event_count,
        repeat_signal,
        underrated_flag,
        first_event_ts,
        last_event_ts
    from yamusic_track_signals
    order by repeat_signal desc, playlist_count desc, title
    limit 5000
    """
)
playlist_signals = query(
    """
    select playlist_title, actual_track_count, unique_track_count, uniqueness_ratio, max_overlap, overlapped_track_mentions, underrated_playlist_flag
    from yamusic_playlist_signals
    order by underrated_playlist_flag desc, uniqueness_ratio desc, actual_track_count desc, playlist_title
    """
)
playlist_overlap = query(
    """
    select playlist_a_title, playlist_b_title, overlap_track_count, jaccard_overlap
    from yamusic_playlist_overlap
    order by jaccard_overlap desc, overlap_track_count desc, playlist_a_title, playlist_b_title
    limit 50
    """
)
genre_periods = query(
    """
    with ranked_genres as (
        select genre
        from yamusic_genre_profile
        order by track_count desc, genre
        limit 10
    )
    select
        gp.activity_month,
        gp.genre,
        gp.event_count,
        gp.event_share_in_month
    from yamusic_genre_periods gp
    join ranked_genres rg using (genre)
    order by gp.activity_month, gp.genre
    """
)
release_eras = query(
    """
    select
        case
            when release_year is null then 'unknown'
            when release_year < 1980 then '<1980'
            when release_year < 1990 then '1980s'
            when release_year < 2000 then '1990s'
            when release_year < 2010 then '2000s'
            when release_year < 2020 then '2010s'
            else '2020s'
        end as era,
        count(*) as track_count,
        sum(case when liked then 1 else 0 end) as liked_track_count,
        round(sum(duration_seconds) / 3600.0, 1) as library_hours
    from yamusic_dim_tracks
    group by 1
    order by
        case era
            when '<1980' then 1
            when '1980s' then 2
            when '1990s' then 3
            when '2000s' then 4
            when '2010s' then 5
            when '2020s' then 6
            else 7
        end
    """
)
playlist_dna = query(
    """
    with top_playlists as (
        select playlist_id, playlist_title, actual_track_count
        from yamusic_playlist_signals
        order by actual_track_count desc, playlist_title
        limit 14
    )
    select
        tp.playlist_title,
        coalesce(t.genre, 'unknown') as genre,
        count(*) as track_count
    from yamusic_fact_playlist_tracks pt
    join top_playlists tp on pt.playlist_id = tp.playlist_id
    left join yamusic_dim_tracks t on pt.track_id = t.track_id
    group by 1, 2
    order by 1, 3 desc, 2
    """
)
time_travel = query(
    """
    select
        title,
        artist_display,
        coalesce(genre, 'unknown') as genre,
        release_year,
        cast(date_trunc('month', first_event_ts) as date) as first_event_month,
        repeat_signal,
        playlist_count,
        liked
    from yamusic_track_signals
    where release_year is not null
      and first_event_ts is not null
    order by repeat_signal desc, playlist_count desc, title
    limit 1500
    """
)
artist_locations = optional_csv(ENRICHMENT_DIR / "artist_locations.csv")
user_location_events = optional_csv(ENRICHMENT_DIR / "user_location_events.csv")

top_artist = first_record(top_artists)
top_genre = first_record(top_genres)
top_overlap = first_record(playlist_overlap)
standout_playlist = first_record(playlist_signals[playlist_signals["underrated_playlist_flag"] == 1])
rediscovery_count = safe_int(row["underrated_tracks"])
liked_share = pct_from_whole(row["liked_tracks"], row["total_tracks"])
source_is_real = str(row["manifest_source"]) == "yandex_music"

genre_options = query(
    """
    select distinct coalesce(genre, 'unknown') as genre
    from yamusic_dim_tracks
    order by genre
    """
)["genre"].tolist()
year_values = track_signals_all["release_year"].dropna().astype(int)
min_year = int(year_values.min()) if not year_values.empty else 1960
max_year = int(year_values.max()) if not year_values.empty else 2026
max_playlist_seen = safe_int(track_signals_all["playlist_count"].max() if not track_signals_all.empty else 0)

st.sidebar.header("Focus controls")
focus_preset = st.sidebar.radio(
    "Quick lens",
    ["Full library", "Liked rediscovery", "Repeat signals", "Playlist repair", "Recent era"],
    help="Presets tune the controls below; change any field after choosing a lens.",
)
default_liked = "All"
default_min_repeat = 0
default_max_playlist = max_playlist_seen
default_years = (min_year, max_year)
if focus_preset == "Liked rediscovery":
    default_liked = "Liked"
    default_max_playlist = 0
elif focus_preset == "Repeat signals":
    default_min_repeat = min(2, safe_int(row["max_repeat_signal"]))
elif focus_preset == "Playlist repair":
    default_max_playlist = min(1, max_playlist_seen)
elif focus_preset == "Recent era":
    default_years = (max(min_year, 2020), max_year)

selected_genres = st.sidebar.multiselect(
    "Genres",
    genre_options,
    default=[],
    placeholder="All genres",
    help="Leave empty to keep every genre in focus.",
)
liked_mode = st.sidebar.selectbox("Liked state", ["All", "Liked", "Not liked"], index=["All", "Liked", "Not liked"].index(default_liked))
track_search = st.sidebar.text_input("Search track, artist, album").strip().lower()
year_range = st.sidebar.slider("Release years", min_year, max_year, default_years)
min_repeat = st.sidebar.slider("Minimum repeat signal", 0, safe_int(row["max_repeat_signal"]), default_min_repeat)
max_playlist_count = st.sidebar.slider("Maximum playlist coverage", 0, max_playlist_seen, default_max_playlist)
filtered_tracks = apply_focus_filters(
    track_signals_all,
    selected_genres,
    liked_mode,
    track_search,
    year_range,
    min_repeat,
    max_playlist_count,
)
st.sidebar.metric("Tracks in focus", compact_int(len(filtered_tracks.index)))
if not filtered_tracks.empty:
    st.sidebar.metric("Artists in focus", compact_int(filtered_tracks["artist_display"].nunique()))
    st.sidebar.metric("Genres in focus", compact_int(filtered_tracks["genre"].fillna("unknown").nunique()))
st.sidebar.caption("The focus controls drive discovery, repeat, artist and explorer views. Top profile cards stay anchored to the complete build.")

cols = st.columns(2)
with cols[0]:
    insight_card(
        "Taste spread",
        f"{compact_int(row['artists'])} artists",
        f"Top artist is only {percent_label(row['top_artist_concentration'])} of the library; this is a broad catalog, not a single-artist archive.",
        "#0f766e",
    )
with cols[1]:
    insight_card(
        "Main genre",
        top_genre.get("genre", "unknown"),
        f"{safe_int(top_genre.get('track_count'))} tracks, {safe_float(top_genre.get('track_share')) * 100:.1f}% of known library weight.",
        "#a16207",
    )
cols = st.columns(2)
with cols[0]:
    insight_card(
        "Rediscovery backlog",
        f"{compact_int(rediscovery_count)} tracks",
        f"{pct_from_whole(rediscovery_count, row['liked_tracks'])} of liked tracks are lightly playlisted or not playlisted.",
        "#c2412d",
    )
with cols[1]:
    overlap_text = "No material overlap detected."
    if top_overlap:
        overlap_text = (
            f"{top_overlap.get('playlist_a_title')} and {top_overlap.get('playlist_b_title')}: "
            f"{safe_float(top_overlap.get('jaccard_overlap')) * 100:.1f}% overlap."
        )
    insight_card("Playlist overlap", f"{compact_int(row['playlists'])} playlists", overlap_text, "#2563eb")

source_label = "Yandex Music" if source_is_real else str(row["manifest_source"])
metric_cols = st.columns(3)
metric_cols[0].metric("Tracks", compact_int(row["total_tracks"]), f"{liked_share} liked")
metric_cols[1].metric("Artists", compact_int(row["artists"]), f"{compact_int(row['known_genres'])} genres")
metric_cols[2].metric("Playlists", compact_int(row["playlists"]), f"{compact_int(row['playlist_track_slots'])} slots")
metric_cols = st.columns(3)
metric_cols[0].metric("Library hours", f"{safe_float(row['library_hours']):.1f}", "metadata duration")
metric_cols[1].metric("Active months", compact_int(row["active_months"]), f"peak {compact_int(row['busiest_month_events'])} events")
metric_cols[2].metric("Source", source_label, "real account" if source_is_real else "sample")

if not has_library_data:
    st.warning("No Yandex Music library metadata was returned for this run.")
    st.code("make ingest\nmake dbt-build", language="bash")

tab_story, tab_taste, tab_atlas, tab_mix, tab_discovery, tab_playlists, tab_tracks, tab_actions, tab_quality = st.tabs(
    ["Story", "Taste Map", "Atlas", "Mix Shift", "Rediscovery", "Playlists", "Explorer", "Actions", "Data Quality"]
)

with tab_story:
    st.subheader("What stands out")
    st.markdown(
        f"""
        <span class="sf-pill">Top artist: {escape(top_artist.get('artist_name', 'unknown'))}</span>
        <span class="sf-pill">Top genre: {escape(top_genre.get('genre', 'unknown'))}</span>
        <span class="sf-pill">Known genres: {compact_int(row['known_genres'])}</span>
        <span class="sf-pill">Max repeat signal: {compact_int(row['max_repeat_signal'])}</span>
        <span class="sf-pill">Data source: {escape(row['manifest_source'])}</span>
        <span class="sf-pill">Focus: {compact_int(len(filtered_tracks.index))} tracks</span>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.25, 1])
    with left:
        st.subheader("Activity timeline")
        st.markdown("<div class='sf-section-note'>Events are metadata events from liked tracks and playlist membership.</div>", unsafe_allow_html=True)
        if not periods.empty:
            period_long = periods.melt(
                id_vars=["activity_month"],
                value_vars=["event_count", "active_tracks", "active_artists"],
                var_name="signal",
                value_name="value",
            )
            timeline = (
                alt.Chart(period_long)
                .mark_line(point=True)
                .encode(
                    x=alt.X("activity_month:T", title=None),
                    y=alt.Y("value:Q", title=None),
                    color=alt.Color("signal:N", title=None),
                    tooltip=["activity_month:T", "signal:N", "value:Q"],
                )
                .properties(height=320)
            )
            st.altair_chart(polish_chart(timeline), use_container_width=True, theme=None)
    with right:
        st.subheader("Genre fingerprint")
        st.markdown("<div class='sf-section-note'>Ranked by track count, with liked coverage retained for comparison.</div>", unsafe_allow_html=True)
        if not top_genres.empty:
            genre_long = top_genres.head(10).melt(
                id_vars=["genre"],
                value_vars=["track_count", "liked_track_count"],
                var_name="measure",
                value_name="tracks",
            )
            chart = (
                alt.Chart(genre_long)
                .mark_bar(cornerRadiusEnd=3)
                .encode(
                    x=alt.X("tracks:Q", title=None),
                    y=alt.Y("genre:N", sort="-x", title=None),
                    color=alt.Color("measure:N", title=None, scale=alt.Scale(range=["#0f766e", "#a16207"])),
                    tooltip=["genre:N", "measure:N", "tracks:Q"],
                )
                .properties(height=320)
            )
            st.altair_chart(polish_chart(chart), use_container_width=True, theme=None)

    with st.expander("Audit rows for Story"):
        display = top_genres.copy()
        display["track_share"] = display["track_share"].map(lambda value: f"{value * 100:.1f}%")
        st.dataframe(display.head(12), use_container_width=True, hide_index=True)
        st.dataframe(periods.sort_values("activity_month", ascending=False), use_container_width=True, hide_index=True)

with tab_taste:
    st.subheader("Artist gravity")
    st.markdown("<div class='sf-section-note'>Artists with more tracks are not necessarily the most liked; the scatter shows breadth versus affinity.</div>", unsafe_allow_html=True)
    artist_map = query(
        """
        select artist_name, track_count, liked_track_count, playlist_appearances
        from yamusic_artist_affinity
        order by track_count desc, liked_track_count desc, artist_name
        limit 150
        """
    )
    if not artist_map.empty:
        artist_map["affinity_rate"] = artist_map["liked_track_count"] / artist_map["track_count"].clip(lower=1)
        artist_chart = (
            alt.Chart(artist_map)
            .mark_circle(opacity=0.72, color="#0f766e")
            .encode(
                x=alt.X("track_count:Q", title="tracks in library"),
                y=alt.Y("liked_track_count:Q", title="liked tracks"),
                size=alt.Size("playlist_appearances:Q", title="playlist appearances", scale=alt.Scale(range=[40, 900])),
                tooltip=["artist_name:N", "track_count:Q", "liked_track_count:Q", "playlist_appearances:Q"],
            )
            .properties(height=420)
        )
        st.altair_chart(polish_chart(artist_chart), use_container_width=True, theme=None)
        fan_col, breadth_col = st.columns(2)
        with fan_col:
            st.subheader("High-affinity artists")
            high_affinity = artist_map[artist_map["track_count"] >= 3].sort_values(
                ["affinity_rate", "liked_track_count", "track_count"],
                ascending=False,
            ).head(8)
            hbar_chart(high_affinity, "affinity_rate", "artist_name", "Liked share among artists with 3+ tracks", "#a16207")
        with breadth_col:
            st.subheader("Catalog anchors")
            hbar_chart(artist_map.head(8), "track_count", "artist_name", "Largest artist footprints", "#2563eb")

    st.subheader("Genre diversity")
    if not top_genres.empty:
        genre_bubble = (
            alt.Chart(top_genres)
            .mark_circle(opacity=0.75, color="#c2412d")
            .encode(
                x=alt.X("track_count:Q", title="tracks"),
                y=alt.Y("liked_track_count:Q", title="liked tracks"),
                size=alt.Size("library_hours:Q", title="library hours", scale=alt.Scale(range=[80, 1200])),
                tooltip=["genre:N", "track_count:Q", "liked_track_count:Q", "library_hours:Q", alt.Tooltip("track_share:Q", format=".1%")],
            )
            .properties(height=360)
        )
        st.altair_chart(polish_chart(genre_bubble), use_container_width=True, theme=None)
    with st.expander("Artist and genre data"):
        genre_table = top_genres.copy()
        if not genre_table.empty:
            genre_table["track_share"] = genre_table["track_share"].map(lambda value: f"{value * 100:.1f}%")
            genre_table["library_hours"] = genre_table["library_hours"].map(lambda value: f"{value:.1f}")
        st.dataframe(artist_map.head(50), use_container_width=True, hide_index=True)
        st.dataframe(genre_table, use_container_width=True, hide_index=True)

with tab_atlas:
    st.subheader("Genre Atlas")
    st.markdown(
        "<div class='sf-section-note'>Not a geographic map: each point is a genre positioned by catalog weight and liked coverage from local metadata.</div>",
        unsafe_allow_html=True,
    )
    atlas_genres = top_genres.copy()
    if not atlas_genres.empty:
        atlas_genres["liked_rate"] = atlas_genres["liked_track_count"] / atlas_genres["track_count"].clip(lower=1)
        atlas_genres["label"] = atlas_genres["genre"].where(atlas_genres["track_count"].rank(method="first", ascending=False) <= 8, "")
        genre_points = (
            alt.Chart(atlas_genres)
            .mark_circle(opacity=0.72)
            .encode(
                x=alt.X("track_share:Q", title="share of known library", axis=alt.Axis(format="%")),
                y=alt.Y("liked_rate:Q", title="liked coverage", axis=alt.Axis(format="%")),
                size=alt.Size("library_hours:Q", title="library hours", scale=alt.Scale(range=[90, 1500])),
                color=alt.Color("track_count:Q", title="tracks", scale=alt.Scale(scheme="goldgreen")),
                tooltip=[
                    "genre:N",
                    "track_count:Q",
                    "liked_track_count:Q",
                    alt.Tooltip("track_share:Q", format=".1%"),
                    alt.Tooltip("liked_rate:Q", format=".1%"),
                    alt.Tooltip("library_hours:Q", format=".1f"),
                ],
            )
        )
        genre_labels = (
            alt.Chart(atlas_genres)
            .mark_text(align="left", baseline="middle", dx=8, color="#17201f", fontSize=12)
            .encode(
                x=alt.X("track_share:Q"),
                y=alt.Y("liked_rate:Q"),
                text="label:N",
            )
        )
        st.altair_chart(polish_chart((genre_points + genre_labels).properties(height=430)), use_container_width=True, theme=None)
    else:
        st.info("No genre profile data for the atlas.")

    st.subheader("Monthly Rhythm")
    st.markdown(
        "<div class='sf-section-note'>A compact rhythm grid from period activity; color intensity is activity volume, not inferred listening location.</div>",
        unsafe_allow_html=True,
    )
    if not periods.empty:
        rhythm = periods.melt(
            id_vars=["activity_month"],
            value_vars=["event_count", "liked_events", "playlist_events", "active_tracks", "active_artists", "active_genres"],
            var_name="signal",
            value_name="value",
        )
        rhythm["signal"] = rhythm["signal"].map(
            {
                "event_count": "all events",
                "liked_events": "liked events",
                "playlist_events": "playlist events",
                "active_tracks": "active tracks",
                "active_artists": "active artists",
                "active_genres": "active genres",
            }
        )
        rhythm_heatmap = (
            alt.Chart(rhythm)
            .mark_rect(cornerRadius=2)
            .encode(
                x=alt.X("yearmonth(activity_month):O", title=None),
                y=alt.Y("signal:N", title=None, sort=["all events", "liked events", "playlist events", "active tracks", "active artists", "active genres"]),
                color=alt.Color("value:Q", title="value", scale=alt.Scale(scheme="tealblues")),
                tooltip=["activity_month:T", "signal:N", "value:Q"],
            )
            .properties(height=260)
        )
        st.altair_chart(polish_chart(rhythm_heatmap), use_container_width=True, theme=None)
    else:
        st.info("No monthly period activity for the rhythm view.")

    st.subheader("Music Time Travel")
    st.markdown(
        "<div class='sf-section-note'>Release year versus first library event month: a way to see whether the library is discovering old catalog or tracking current releases.</div>",
        unsafe_allow_html=True,
    )
    if not time_travel.empty:
        time_travel_chart = (
            alt.Chart(time_travel)
            .mark_circle(opacity=0.55)
            .encode(
                x=alt.X("release_year:Q", title="release year", scale=alt.Scale(zero=False)),
                y=alt.Y("first_event_month:T", title="first library event"),
                size=alt.Size("repeat_signal:Q", title="repeat signal", scale=alt.Scale(range=[25, 700])),
                color=alt.Color("genre:N", title="genre", legend=None),
                tooltip=["title:N", "artist_display:N", "genre:N", "release_year:Q", "first_event_month:T", "repeat_signal:Q", "playlist_count:Q"],
            )
            .properties(height=390)
        )
        st.altair_chart(polish_chart(time_travel_chart), use_container_width=True, theme=None)
    else:
        st.info("No release-year and event-month pairs are available for time travel.")

    st.subheader("Playlist Subway")
    st.markdown(
        "<div class='sf-section-note'>Lines connect playlists with shared tracks; thicker lines mean higher Jaccard overlap.</div>",
        unsafe_allow_html=True,
    )
    subway_nodes, subway_edges = playlist_subway_frames(playlist_overlap)
    if not subway_nodes.empty and not subway_edges.empty:
        edge_chart = (
            alt.Chart(subway_edges)
            .mark_rule(opacity=0.58, color="#66736f")
            .encode(
                x=alt.X("x_a:Q", title=None, axis=None),
                y=alt.Y("y_a:Q", title=None, axis=None, scale=alt.Scale(reverse=True)),
                x2="x_b:Q",
                y2="y_b:Q",
                size=alt.Size("jaccard_overlap:Q", title="overlap", scale=alt.Scale(range=[1, 9])),
                tooltip=[
                    "pair:N",
                    "overlap_track_count:Q",
                    alt.Tooltip("jaccard_overlap:Q", format=".1%"),
                ],
            )
        )
        node_chart = (
            alt.Chart(subway_nodes)
            .mark_circle(color="#0f766e", opacity=0.88)
            .encode(
                x=alt.X("x:Q", title=None, axis=None),
                y=alt.Y("y:Q", title=None, axis=None, scale=alt.Scale(reverse=True)),
                size=alt.Size("connection_count:Q", title="connections", scale=alt.Scale(range=[180, 900])),
                tooltip=[
                    "playlist_title:N",
                    "connection_count:Q",
                    "overlap_tracks:Q",
                    alt.Tooltip("max_jaccard:Q", format=".1%"),
                ],
            )
        )
        node_labels = (
            alt.Chart(subway_nodes)
            .mark_text(align="left", baseline="middle", dx=12, color="#17201f", fontSize=12)
            .encode(x="x:Q", y=alt.Y("y:Q", scale=alt.Scale(reverse=True)), text="playlist_title:N")
        )
        st.altair_chart(polish_chart((edge_chart + node_chart + node_labels).properties(height=380)), use_container_width=True, theme=None)
    else:
        st.info("No playlist overlap edges are available for the subway view.")

    st.subheader("Playlist DNA")
    st.markdown(
        "<div class='sf-section-note'>A matrix of playlist composition by genre. This is more useful than overlap when only a few playlists share tracks directly.</div>",
        unsafe_allow_html=True,
    )
    if not playlist_dna.empty:
        dna_chart = (
            alt.Chart(playlist_dna)
            .mark_rect()
            .encode(
                x=alt.X("genre:N", title=None, sort="-y"),
                y=alt.Y("playlist_title:N", title=None, sort="-x"),
                color=alt.Color("track_count:Q", title="tracks", scale=alt.Scale(scheme="goldgreen")),
                tooltip=["playlist_title:N", "genre:N", "track_count:Q"],
            )
            .properties(height=max(280, min(620, playlist_dna["playlist_title"].nunique() * 34)))
        )
        st.altair_chart(polish_chart(dna_chart), use_container_width=True, theme=None)
    else:
        st.info("No playlist DNA rows are available.")

    st.subheader("Geo Atlas readiness")
    st.markdown(
        "<div class='sf-section-note'>Maps stay opt-in. Current Yandex Music metadata has no listening location, so map layers need user-provided location timelines or artist-location enrichment.</div>",
        unsafe_allow_html=True,
    )
    geo_cols = st.columns(2)
    geo_cols[0].metric("Artist location rows", compact_int(len(artist_locations.index)))
    geo_cols[1].metric("User location rows", compact_int(len(user_location_events.index)))
    if not artist_locations.empty and {"latitude", "longitude"}.issubset(artist_locations.columns):
        st.caption("Artist-associated geography. This is not evidence of where you listened.")
        artist_map = artist_locations.rename(columns={"latitude": "lat", "longitude": "lon"}).copy()
        st.map(artist_map[["lat", "lon"]].dropna())
    elif not user_location_events.empty and {"latitude", "longitude"}.issubset(user_location_events.columns):
        st.caption("User-provided location timeline. Events need timestamp matching before this becomes a listening map.")
        user_map = user_location_events.rename(columns={"latitude": "lat", "longitude": "lon"}).copy()
        st.map(user_map[["lat", "lon"]].dropna())
    else:
        st.info(
            "Add `data/enrichment/artist_locations.csv` or `data/enrichment/user_location_events.csv` "
            "with `latitude` and `longitude` columns to unlock map previews."
        )
        st.code(
            "artist_name,city,country_code,latitude,longitude,confidence,source\n"
            "Oxxxymiron,London,GB,51.5072,-0.1276,0.6,manual\n\n"
            "started_at,ended_at,city,country_code,latitude,longitude,confidence,source\n"
            "2024-08-01T00:00:00Z,2024-08-15T00:00:00Z,Tbilisi,GE,41.7151,44.8271,0.8,manual_city_timeline",
            language="csv",
        )

    with st.expander("Atlas source rows"):
        if not atlas_genres.empty:
            atlas_table = atlas_genres.drop(columns=["label"], errors="ignore").copy()
            atlas_table["track_share"] = atlas_table["track_share"].map(lambda value: f"{value * 100:.1f}%")
            atlas_table["liked_rate"] = atlas_table["liked_rate"].map(lambda value: f"{value * 100:.1f}%")
            st.dataframe(atlas_table, use_container_width=True, hide_index=True)
        if not periods.empty:
            st.dataframe(periods, use_container_width=True, hide_index=True)
        if not playlist_overlap.empty:
            overlap_table = playlist_overlap.copy()
            overlap_table["jaccard_overlap"] = overlap_table["jaccard_overlap"].map(lambda value: f"{value * 100:.1f}%")
            st.dataframe(overlap_table, use_container_width=True, hide_index=True)
        if not playlist_dna.empty:
            st.dataframe(playlist_dna, use_container_width=True, hide_index=True)
        if not time_travel.empty:
            st.dataframe(time_travel.head(200), use_container_width=True, hide_index=True)

with tab_mix:
    st.subheader("Genre heatmap")
    st.markdown("<div class='sf-section-note'>A Wrapped-style view of when genres entered the library metadata stream.</div>", unsafe_allow_html=True)
    if not genre_periods.empty:
        heatmap = (
            alt.Chart(genre_periods)
            .mark_rect()
            .encode(
                x=alt.X("yearmonth(activity_month):O", title=None),
                y=alt.Y("genre:N", title=None),
                color=alt.Color("event_count:Q", title="events", scale=alt.Scale(scheme="tealblues")),
                tooltip=["activity_month:T", "genre:N", "event_count:Q", alt.Tooltip("event_share_in_month:Q", format=".1%")],
            )
            .properties(height=360)
        )
        st.altair_chart(polish_chart(heatmap), use_container_width=True, theme=None)

    left, right = st.columns(2)
    with left:
        st.subheader("Release-era mix")
        era_long = release_eras.melt(
            id_vars=["era"],
            value_vars=["track_count", "liked_track_count"],
            var_name="measure",
            value_name="tracks",
        )
        era_chart = (
            alt.Chart(era_long)
            .mark_bar(cornerRadiusEnd=3)
            .encode(
                x=alt.X("tracks:Q", title=None),
                y=alt.Y("era:N", sort=["<1980", "1980s", "1990s", "2000s", "2010s", "2020s", "unknown"], title=None),
                color=alt.Color("measure:N", title=None, scale=alt.Scale(range=["#2563eb", "#0f766e"])),
                tooltip=["era:N", "measure:N", "tracks:Q"],
            )
            .properties(height=300)
        )
        st.altair_chart(polish_chart(era_chart), use_container_width=True, theme=None)
    with right:
        st.subheader("Focus genre mix")
        focus_genres = (
            filtered_tracks.assign(genre=filtered_tracks["genre"].fillna("unknown"))
            .groupby("genre", as_index=False)
            .agg(track_count=("title", "count"), repeat_signal=("repeat_signal", "sum"))
            .sort_values("track_count", ascending=False)
            .head(10)
        )
        hbar_chart(focus_genres, "track_count", "genre", "Tracks in the current focus", "#0f766e")

with tab_discovery:
    st.subheader("Rediscovery queue")
    st.markdown(
        "<div class='sf-section-note'>Liked tracks with low playlist coverage are good candidates for resurfacing or playlist repair.</div>",
        unsafe_allow_html=True,
    )
    rediscovery = filtered_tracks[filtered_tracks["underrated_flag"] == 1].sort_values(
        ["playlist_count", "repeat_signal", "title"],
        ascending=[True, False, True],
    )
    c1, c2, c3 = st.columns(3)
    c1.metric("Filtered rediscovery tracks", compact_int(len(rediscovery.index)))
    c2.metric("Zero-playlist liked tracks", compact_int((rediscovery["playlist_count"] == 0).sum() if not rediscovery.empty else 0))
    c3.metric("Top repeat in queue", compact_int(rediscovery["repeat_signal"].max() if not rediscovery.empty else 0))

    st.subheader("Rediscovery quadrants")
    st.markdown(
        "<div class='sf-section-note'>High repeat and low playlist coverage is the most actionable corner: tracks you seem to return to but have not organized.</div>",
        unsafe_allow_html=True,
    )
    if not filtered_tracks.empty:
        quadrant_chart = (
            alt.Chart(filtered_tracks)
            .mark_circle(opacity=0.56)
            .encode(
                x=alt.X("playlist_count:Q", title="playlist coverage"),
                y=alt.Y("repeat_signal:Q", title="repeat signal"),
                size=alt.Size("event_count:Q", title="library events", scale=alt.Scale(range=[20, 650])),
                color=alt.Color("liked:N", title="liked", scale=alt.Scale(range=["#a16207", "#0f766e"])),
                tooltip=["title:N", "artist_display:N", "genre:N", "playlist_count:Q", "repeat_signal:Q", "event_count:Q"],
            )
            .properties(height=360)
        )
        st.altair_chart(polish_chart(quadrant_chart), use_container_width=True, theme=None)

    render_track_cards(rediscovery, limit=8)

    st.subheader("Repeat signals")
    repeats = filtered_tracks.sort_values(["repeat_signal", "playlist_count", "event_count"], ascending=False).head(40)
    if not repeats.empty:
        repeat_chart = repeats.head(15).copy()
        repeat_chart["track"] = repeat_chart["title"] + " · " + repeat_chart["artist_display"]
        hbar_chart(repeat_chart, "repeat_signal", "track", "Repeat signal leaderboard", "#c2412d")
    with st.expander("Rediscovery and repeat rows"):
        st.dataframe(
            rediscovery[["title", "artist_display", "genre", "playlist_count", "event_count", "repeat_signal"]].head(250),
            use_container_width=True,
            hide_index=True,
        )
        st.dataframe(
            repeats[["title", "artist_display", "genre", "liked", "playlist_count", "event_count", "repeat_signal"]],
            use_container_width=True,
            hide_index=True,
        )

with tab_playlists:
    st.subheader("Playlist health")
    st.markdown("<div class='sf-section-note'>High uniqueness plus low overlap suggests a playlist is a distinct listening surface.</div>", unsafe_allow_html=True)
    playlist_viz = playlist_signals.copy()
    if not playlist_viz.empty:
        playlist_viz["health_score"] = playlist_viz["uniqueness_ratio"] * (1 - playlist_viz["max_overlap"])
        playlist_viz["status"] = playlist_viz["underrated_playlist_flag"].map(lambda value: "standout" if value else "normal")
        playlist_chart = (
            alt.Chart(playlist_viz)
            .mark_circle(opacity=0.78)
            .encode(
                x=alt.X("uniqueness_ratio:Q", title="uniqueness", axis=alt.Axis(format="%")),
                y=alt.Y("max_overlap:Q", title="max overlap", axis=alt.Axis(format="%")),
                size=alt.Size("actual_track_count:Q", title="tracks", scale=alt.Scale(range=[80, 1100])),
                color=alt.Color("status:N", title=None, scale=alt.Scale(range=["#0f766e", "#c2412d"])),
                tooltip=["playlist_title:N", "actual_track_count:Q", alt.Tooltip("uniqueness_ratio:Q", format=".1%"), alt.Tooltip("max_overlap:Q", format=".1%")],
            )
            .properties(height=420)
        )
        st.altair_chart(polish_chart(playlist_chart), use_container_width=True, theme=None)
        standout = playlist_viz.sort_values(["health_score", "actual_track_count"], ascending=False).head(6)
        hbar_chart(standout, "health_score", "playlist_title", "Most distinct playlist surfaces", "#0f766e")

    st.subheader("Playlist overlap")
    overlap = playlist_overlap.copy()
    if not overlap.empty:
        overlap["pair"] = overlap["playlist_a_title"] + " / " + overlap["playlist_b_title"]
        hbar_chart(overlap.head(15), "jaccard_overlap", "pair", "Potential cleanup pairs", "#a16207")
    with st.expander("Playlist rows"):
        playlist_table = playlist_signals.copy()
        playlist_table["uniqueness_ratio"] = playlist_table["uniqueness_ratio"].map(lambda value: f"{value * 100:.1f}%")
        playlist_table["max_overlap"] = playlist_table["max_overlap"].map(lambda value: f"{value * 100:.1f}%")
        playlist_table["underrated_playlist_flag"] = playlist_table["underrated_playlist_flag"].map(lambda value: "yes" if value else "no")
        if not overlap.empty:
            overlap["jaccard_overlap"] = overlap["jaccard_overlap"].map(lambda value: f"{value * 100:.1f}%")
        st.dataframe(playlist_table, use_container_width=True, hide_index=True)
        st.dataframe(overlap.drop(columns=["pair"], errors="ignore"), use_container_width=True, hide_index=True)

with tab_tracks:
    st.subheader("Explorer")
    st.markdown("<div class='sf-section-note'>A visual browse surface for the active focus. Tables stay collapsed for exact lookup.</div>", unsafe_allow_html=True)
    e1, e2, e3 = st.columns(3)
    e1.metric("Tracks in focus", compact_int(len(filtered_tracks.index)))
    e2.metric("Liked in focus", compact_int(filtered_tracks["liked"].sum() if not filtered_tracks.empty else 0))
    e3.metric("Zero-playlist", compact_int((filtered_tracks["playlist_count"] == 0).sum() if not filtered_tracks.empty else 0))
    render_track_cards(filtered_tracks.sort_values(["liked", "repeat_signal", "playlist_count"], ascending=[False, False, True]), limit=12)
    with st.expander("Exact track lookup"):
        st.dataframe(
            filtered_tracks[["title", "artist_display", "album_title", "genre", "release_year", "liked", "playlist_count", "repeat_signal"]],
            use_container_width=True,
            hide_index=True,
        )

with tab_actions:
    st.subheader("Next actions")
    for action in build_data_next_actions(row.to_dict()):
        st.write(f"- {action}")

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

    st.subheader("Action previews")
    left, right = st.columns(2)
    with left:
        st.caption("Playlist cleanup candidates")
        cleanup = playlist_overlap.copy()
        if not cleanup.empty:
            cleanup["jaccard_overlap"] = cleanup["jaccard_overlap"].map(lambda value: f"{value * 100:.1f}%")
        st.dataframe(cleanup.head(25), use_container_width=True, hide_index=True)
    with right:
        st.caption("Standout playlists")
        standout = playlist_signals[playlist_signals["underrated_playlist_flag"] == 1].copy()
        if not standout.empty:
            standout["uniqueness_ratio"] = standout["uniqueness_ratio"].map(lambda value: f"{value * 100:.1f}%")
            standout["max_overlap"] = standout["max_overlap"].map(lambda value: f"{value * 100:.1f}%")
        st.dataframe(standout.head(25), use_container_width=True, hide_index=True)

with tab_quality:
    st.subheader("Local data quality signals")
    q1, q2, q3, q4 = st.columns(4)
    q1.metric("Raw tracks", compact_int(row["raw_tracks"]))
    q2.metric("Fetch failures", compact_int(row["diagnostic_liked_shortcuts_fetch_failed"] + row["diagnostic_playlist_tracks_fetch_failed"]))
    q3.metric("Duplicate skips", compact_int(row["diagnostic_liked_tracks_duplicate_skipped"] + row["diagnostic_playlist_tracks_duplicate_skipped"]))
    q4.metric("Stale", yes_no(row["stale_ingestion_flag"]))
    st.json(source_payload(row))
    st.info("Run `make test` for schema, relationship, compile and compose checks.")
