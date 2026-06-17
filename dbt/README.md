# dbt-модели Streamify

Этот dbt-проект собирает локальные DuckDB-марты для self-analytics Яндекс Музыки.

## Запуск

```bash
dbt deps
dbt build --profiles-dir . --target local --select yamusic
```

Для обычной локальной работы запускайте из корня репозитория:

```bash
make dbt-build
```

## Состав моделей

- `staging/stg_yamusic_*`: typed views over raw JSONL metadata and the ingestion manifest.
- `marts/yamusic_dim_*`: track, artist, album and playlist dimensions.
- `marts/yamusic_fact_*`: library events and playlist-track membership.
- `marts/yamusic_*_signals`: practical self-analytics for affinity, repeats, genres, periods, playlists and library health.

Локальный профиль по умолчанию пишет в `data/streamify.duckdb` и читает raw metadata из `data/raw/yamusic`.
