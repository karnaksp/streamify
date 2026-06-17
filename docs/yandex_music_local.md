# Локальная аналитика Яндекс Музыки

Streamify собирает личный music self-analytics lakehouse из метаданных Яндекс Музыки. Он рассчитан на запуск на ноутбуке, без cloud credentials и облачных расходов.

Проект не скачивает, не хранит, не преобразует и не воспроизводит аудио. Ingestion-адаптер читает только метаданные, доступные аккаунту через клиентскую библиотеку Яндекс Музыки.

## Быстрый старт

```bash
cp .env.example .env
make setup
make help
make status
make ingest-sample
make raw-contract
make dbt-build
make doctor
make report
make readiness
make dashboard-smoke
make dashboard
```

To use real account metadata, set `YANDEX_MUSIC_TOKEN` in `.env` and run:

```bash
make acceptance-real
make dashboard
```

## Токен Яндекс Музыки

Streamify does not ask for your Yandex password and does not fetch a token by itself. The installed `yandex-music` Python client accepts an existing OAuth token through `Client(token).init()`, but version 2.2.0 does not expose a `device_auth` helper.

Run `make token-help` for the in-repo token setup helper. It checks whether `.env` exists, whether a token is configured, the installed `yandex-music` client version and whether that client exposes a built-in device auth flow. It never prints token values.

Use an external Yandex Music OAuth token helper, then paste only the resulting token into the local `.env` file:

```env
YANDEX_MUSIC_TOKEN=your_oauth_token_here
```

Известный community helper:

- `https://github.com/MarshalX/yandex-music-token`

Treat the token as a password. Do not commit `.env`, paste the token into chat, or add it to any tracked config. After saving `.env`, validate access without writing raw data:

```bash
make preflight
```

The Python CLI and support scripts load `.env` directly. The Makefile invokes commands through `scripts/run_with_dotenv.py`, so `YANDEX_MUSIC_TOKEN`, `STREAMIFY_RAW_DIR`, `STREAMIFY_DUCKDB_PATH`, `STREAMIFY_REPORT_PATH`, `STREAMIFY_SNAPSHOT_PATH`, `STREAMIFY_RECOMMENDATIONS_DIR`, `STREAMIFY_DASHBOARD_PORT`, and `DBT_THREADS` behave the same in direct commands and `make` targets without Make parsing token values.

Run `make help` when you want the shortest command map for sample metadata, real-account metadata, Docker Compose, exports, readiness and cleanup.

The Yandex Music adapter uses bounded retries around client initialization, account-level API calls, playlist hydration and liked-track hydration. A transient failure should not immediately break `make preflight` or `make ingest`; repeated failures still surface as sanitized `YandexMusicIngestError` messages without printing the token.

Run `make status` before a real account run when you want a safe local diagnostic. It reports whether `.env` exists, whether a token is configured, where raw/DuckDB/report/snapshot/recommendations artifacts are expected, the latest manifest source/timestamp when available, and the next command to run. It does not call Yandex Music and does not print token values.

The Docker path uses the `local` profile. `make up-local` loads `.env` through `scripts/run_with_dotenv.py` before invoking Docker Compose, so token values are passed through the process environment instead of Make parsing. The one-shot `streamify-local` service falls back to sample data when the token is empty and runs with `set -euo pipefail`, so a failed ingestion/dbt/quality step stops the stack instead of continuing on stale files. When a token is present, the readiness audit uses `--require-real`; otherwise it validates the deterministic sample path. The service runs ingestion, raw contract validation, dbt build, doctor, static report export, and readiness audit before the dashboard starts:

```bash
make up-local
```

For an automated Docker smoke test that does not call a real account, run:

```bash
make compose-smoke-local
```

After `YANDEX_MUSIC_TOKEN` is configured, verify the same Docker Compose profile against real account metadata:

```bash
make compose-smoke-real
```

The local dbt command is:

```bash
cd dbt && dbt build --profiles-dir . --target local --select yamusic
```

For normal use, prefer `make dbt-build`: it runs `dbt deps` first, so a fresh checkout does not depend on an existing ignored `dbt/dbt_packages` directory.

## Data Flow

1. `yamusic_ingest` writes normalized JSONL files plus `_manifest.json` into `data/raw/yamusic`.
2. dbt DuckDB reads those JSONL files with typed `read_json` schemas so empty/private account files still compile predictably.
3. Staging models deduplicate tracks, artists, albums, playlists, playlist membership and library events.
4. Mart models produce track, artist, album, playlist, library-event, affinity, period, genre, genre-period, overlap and track-signal tables.
5. `dashboard/app.py` reads `data/streamify.duckdb` and presents the self-analytics workspace.
6. `scripts/export_yamusic_summary.py` writes `data/streamify_summary.md` for a portable answer-first summary.
7. `scripts/export_yamusic_snapshot.py` writes `data/streamify_snapshot.json` for automation, CI artifacts and downstream agent workflows.
8. `scripts/export_yamusic_recommendations.py` writes practical CSV queues into `data/recommendations`.

See [Yandex Music Local Lineage](yamusic_lineage.md) for the raw-to-dashboard model catalog and product-question mapping.

## Проверка реального аккаунта

After setting `YANDEX_MUSIC_TOKEN`, a successful real-account run should satisfy this checklist:

- `make acceptance-real` completes end-to-end;
- `make ingest` exits successfully without printing the token;
- `make preflight` returns Yandex Music access counts without writing raw data or printing the token;
- `data/raw/yamusic/tracks.jsonl` exists and contains account metadata rows, or the CLI clearly reports that the account/API returned no rows;
- `make dbt-build` completes with the `local` DuckDB target;
- `make dashboard` opens and shows either non-empty metrics or a clear no-data state;
- no audio files are created under `data/`.

Empty/private accounts are a supported state. The dbt smoke test builds against empty raw JSONL files, and the dashboard shows `No Yandex Music library metadata was returned for this run.` when `yamusic_library_profile.total_tracks` is zero.

## Raw Datasets

- `tracks.jsonl`: track metadata, album fields, artist arrays and liked flag.
- `artists.jsonl`: normalized artist metadata discovered through tracks and account-visible liked artists.
- `albums.jsonl`: normalized album metadata discovered through tracks and account-visible liked albums.
- `playlists.jsonl`: owned playlist metadata plus account-visible liked playlist metadata and declared track counts when available.
- `playlist_tracks.jsonl`: playlist-track membership.
- `user_library_events.jsonl`: derived events for liked tracks and playlist membership.
- `_manifest.json`: source, generated timestamp, adapter/client metadata, row counts, JSONL checksums and output paths; it must not contain token material.
- `_manifest.json.diagnostics`: aggregate skip/fallback counters for liked-track hydration, liked album/artist/playlist metadata, playlist hydration, playlist-track hydration, missing IDs, duplicate liked shortcuts and duplicate playlist-track memberships; these are counts only and do not store skipped object identifiers. A `*_fetch_failed` counter means full metadata enrichment failed after retries, not necessarily that the library row was dropped.

## Продуктовые ответы

The local marts are designed around practical self-analytics questions:

- favorite artists and tracks: `yamusic_artist_affinity`, `yamusic_dim_tracks`;
- genre shifts and diversity: `yamusic_genre_profile`, `yamusic_genre_periods`, `yamusic_period_activity`;
- repeated patterns: `yamusic_track_signals.repeat_signal`;
- active periods: `yamusic_period_activity`;
- underrated tracks: liked tracks with low playlist coverage in `yamusic_track_signals`;
- underrated playlists: high-uniqueness, low-overlap playlists in `yamusic_playlist_signals`;
- playlist overlap: pairwise Jaccard similarity in `yamusic_playlist_overlap`.

The dashboard includes sidebar focus controls for genre, liked state, text search, release years, repeat signal and playlist coverage. These filters apply to track-level discovery views such as repeated/underrated tracks and the visual Explorer. The Atlas tab adds chart-first views for genre shape, monthly rhythm, release-year time travel, playlist subway overlap and playlist DNA. The Actions tab turns the marts into next-step queues: real-account/data-quality actions, rediscovery tracks, playlist cleanup candidates, standout playlists, and download buttons for the markdown summary, JSON snapshot and recommendations CSV files.

Location-aware analytics are intentionally out of scope for the current Yandex Music metadata adapter. Yandex Music library metadata does not provide a stable listening location, and account region, playlist language, genre or artist origin must not be treated as user location. The dashboard can show Geo Atlas readiness and optional map previews when user-supplied CSV enrichment exists under `STREAMIFY_ENRICHMENT_DIR`, but those maps must be labeled as artist-associated geography or user-provided location timeline data. A future opt-in contract for user-supplied location timelines and artist-associated places is documented in [Future Location Enrichment Contract](location_enrichment.md).

`make report` exports the same marts into two portable artifacts:

- `data/streamify_summary.md`: executive summary, top artists, genre shifts, repeat signals, underrated tracks, underrated playlists, next steps and caveats.
- `data/streamify_snapshot.json`: schema-versioned JSON with profile metrics, raw counts, ingestion diagnostics, favorite artists/tracks, genre shifts, active periods, repeat tracks, playlist overlap, underrated candidates and next actions.
- `data/recommendations/*.csv`: spreadsheet-friendly exports for top artists, rediscovery tracks, playlist cleanup, standout playlists and genre shifts.

## Качество данных

The local dbt layer checks:

- non-null and unique track, artist, playlist and event keys;
- playlist-track relationships back to playlist and track dimensions;
- accepted values for derived event types;
- duplicate control through staging dedupe;
- stale Parquet cleanup on empty or `--json-only` ingestion reruns, so raw metadata outputs reflect the latest run rather than leftovers from an earlier run.
- genre-period uniqueness by month and genre in `yamusic_genre_periods`.
- track-signal checks for repeat and underrated flags.
- stale ingestion visibility through `yamusic_library_profile.stale_ingestion_flag`, which is raised when the newest local library event is older than 168 hours or missing.
- bounded retries on external Yandex Music client calls, with unit coverage for transient preflight and track-fetch failures.
- raw JSONL checksums and ingestion diagnostics in the manifest, DuckDB profile, readiness JSON, dashboard Data Quality tab, JSON snapshot and static report.

`scripts/check_no_local_sensitive_artifacts.py` fails when root `.env`, local Yandex raw data, DuckDB warehouse files, or audio files under `data/` are tracked by git. `.env.example` remains safe to commit because it contains an empty token placeholder.

`make raw-contract` validates the bronze/raw JSONL shape before dbt reads it: required fields, basic JSON types, allowed `source` values, accepted library event types, manifest row counts, JSONL sha256 checksums, ingestion diagnostics consistency, unique IDs, and playlist/event referential integrity. Empty/private accounts remain valid when the files exist and contain zero rows.

`make doctor` runs local acceptance checks against the latest raw metadata and DuckDB marts: manifest row counts, JSONL validity, required mart tables, one-row library profile, no missing self-analytics tables, source/raw-count alignment between `_manifest.json` and `yamusic_library_profile`, and non-empty signal tables when account data exists.

`make readiness` emits a JSON readiness summary for the current local product artifact: source type, raw row counts, DuckDB profile counts, report path, snapshot path, recommendations directory, no-audio status, stale-dbt protection, and whether the latest run proves real-account ingestion. `make readiness-real` uses the same audit with `--require-real` and fails unless `_manifest.json` declares `source=yandex_music`.

`make acceptance-real` is the final real-account gate. It runs `make preflight`, `make ingest`, raw contract validation, dbt deps/build, `make doctor`, `make report`, `make readiness-real`, and `make dashboard-smoke` against the configured `YANDEX_MUSIC_TOKEN`.

`make dashboard-smoke` runs a Streamlit content smoke with `streamlit.testing.v1.AppTest` to verify the expected self-analytics title, metrics, tabs, sections, dataframes and Data Quality JSON block. It then starts Streamlit against the local DuckDB file and verifies that the dashboard returns HTTP 200. Browser QA is still useful for visual regressions, but this gives a fast command-line guard for both content and app startup.

`make compose-smoke-local` runs the Docker Compose `local` profile with a deterministic empty token, verifies that the dashboard returns HTTP 200 after the one-shot ingestion/dbt/doctor/report/readiness service succeeds, then validates the mounted raw contract, readiness JSON, product-answer exports and dashboard content smoke before tearing the stack down.

## Limitations

Yandex Music does not provide a stable public API for every analytics use case. This project isolates integration behind `yamusic_ingest/yandex_client.py` and uses the unofficial `yandex-music` Python package. Available fields can differ by account, region, subscription state, and library visibility.

If the real integration returns less data than expected, use `make ingest-sample` to verify the local pipeline and dashboard independently from account access.

The local product does not infer where listening happened. Future location enrichment must come from explicit user-provided sources, such as Google Takeout Location History when available, selected photo EXIF, calendar/travel exports, a manual city timeline, or network/IP logs only when the user deliberately supplies them. iOS Significant Locations may exist on-device but are not practically exportable for this product. See [Future Location Enrichment Contract](location_enrichment.md) for schema ideas, privacy constraints and timestamp-join caveats.

## Reset

```bash
make clean-local
make ingest-sample
make dbt-build
```

`make clean-local` removes generated raw metadata, DuckDB databases, static summary/snapshot reports, recommendations CSV files, dbt `target`/`logs`/`dbt_packages`, and smoke-test artifacts such as `streamify_empty_smoke`. It does not remove `.env`, token configuration, source files, or documentation.
