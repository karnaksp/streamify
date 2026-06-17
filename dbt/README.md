# Streamify dbt Models

This dbt project builds local DuckDB marts for Yandex Music self-analytics.

## Run

```bash
dbt deps
dbt build --profiles-dir . --target local --select yamusic
```

For normal local work, run from the repository root:

```bash
make dbt-build
```

## Model Shape

- `staging/stg_yamusic_*`: typed views over raw JSONL metadata and the ingestion manifest.
- `marts/yamusic_dim_*`: track, artist, album and playlist dimensions.
- `marts/yamusic_fact_*`: library events and playlist-track membership.
- `marts/yamusic_*_signals`: practical self-analytics for affinity, repeats, genres, periods, playlists and library health.

The local profile writes to `data/streamify.duckdb` by default and reads raw metadata from `data/raw/yamusic`.
