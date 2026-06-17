from __future__ import annotations

import pandas as pd


def apply_track_filters(frame: pd.DataFrame, genres: list[str], liked_mode: str, search_text: str) -> pd.DataFrame:
    filtered = frame.copy()
    if "genre" in filtered.columns and genres:
        filtered = filtered[filtered["genre"].fillna("unknown").isin(genres)]
    if "liked" in filtered.columns and liked_mode == "Liked":
        filtered = filtered[filtered["liked"] == True]  # noqa: E712
    if "liked" in filtered.columns and liked_mode == "Not liked":
        filtered = filtered[filtered["liked"] == False]  # noqa: E712
    search = search_text.strip().lower()
    if search:
        searchable_columns = [column for column in ["title", "artist_display", "album_title"] if column in filtered.columns]
        if searchable_columns:
            mask = pd.Series(False, index=filtered.index)
            for column in searchable_columns:
                mask = mask | filtered[column].fillna("").str.lower().str.contains(search, regex=False)
            filtered = filtered[mask]
    return filtered
