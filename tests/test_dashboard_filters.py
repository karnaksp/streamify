from __future__ import annotations

import pandas as pd

from dashboard.filters import apply_track_filters


def track_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"title": "Signal One", "artist_display": "Nadia Vector", "album_title": "Local Lake", "genre": "electronic", "liked": True},
            {"title": "Blue Warehouse", "artist_display": "Duck DB Trio", "album_title": "Warehouse Sketches", "genre": "jazz", "liked": True},
            {"title": "Quiet Branch", "artist_display": "The Lineage", "album_title": "Local Lake", "genre": "electronic", "liked": False},
        ]
    )


def test_apply_track_filters_by_genre_and_liked() -> None:
    result = apply_track_filters(track_frame(), ["electronic"], "Liked", "")

    assert result["title"].tolist() == ["Signal One"]


def test_apply_track_filters_searches_title_artist_and_album_case_insensitively() -> None:
    by_artist = apply_track_filters(track_frame(), ["electronic", "jazz"], "All", "nadia")
    by_album = apply_track_filters(track_frame(), ["electronic", "jazz"], "All", "warehouse")

    assert by_artist["title"].tolist() == ["Signal One"]
    assert by_album["title"].tolist() == ["Blue Warehouse"]


def test_apply_track_filters_not_liked() -> None:
    result = apply_track_filters(track_frame(), ["electronic", "jazz"], "Not liked", "")

    assert result["title"].tolist() == ["Quiet Branch"]
