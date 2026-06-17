# Streamify Local Product Acceptance

This document maps the MVP requirements to concrete repository artifacts and verification commands. The local product is considered ready for sample metadata after `make test` passes. It is considered ready for a real account only after `make acceptance-real` passes with a valid `YANDEX_MUSIC_TOKEN`.

## Requirement Matrix

| Requirement | Implementation Evidence | Verification |
| --- | --- | --- |
| Fully local run without GCP | `Makefile`, `docker-compose.local.yml`, `dbt/profiles.yml` local DuckDB target | `make acceptance-local`, `make compose-smoke-local` |
| Local operator entrypoint | `make help` lists sample, real-account, Docker, export, readiness and cleanup commands | `make help` |
| Docker Compose local product path | `docker-compose.local.yml` `local` profile with one-shot build, dashboard services, `set -euo pipefail`, real-source readiness enforcement when a token is configured, and compose smoke validation of raw/product/dashboard artifacts | `make up-local`, `make compose-smoke-local`, `make compose-smoke-real` |
| Yandex Music metadata ingestion | `yamusic_ingest/__main__.py`, `yamusic_ingest/yandex_client.py`; liked tracks, owned playlists, liked playlists, liked albums and liked artists where exposed by the API | `make preflight`, `make ingest`, `make acceptance-real` |
| No audio download or storage | metadata-only adapter, `.gitignore`, safety scripts | `scripts/check_no_audio_artifacts.py`, `scripts/check_no_local_sensitive_artifacts.py` |
| Raw normalized outputs | `tracks`, `artists`, `albums`, `playlists`, `playlist_tracks`, `user_library_events` JSONL/Parquet writers | `make ingest-sample`, `make raw-contract` |
| Bronze/silver/gold data engineering path | `data/raw/yamusic`, `stg_yamusic_*`, `yamusic_dim_*`, `yamusic_fact_*`, profile/signal marts | `make dbt-build`, `make doctor` |
| Source provenance and stale-build protection | `stg_yamusic_manifest`, manifest fields in `yamusic_library_profile`, doctor/readiness raw-count alignment checks | `make doctor`, `make readiness`, `make product-answers-smoke` |
| Idempotent local ingestion | overwrite-per-run raw writer, stale Parquet cleanup, and `_manifest.json` row counts | repeated `make ingest-sample`, `make raw-contract` |
| Data quality checks | dbt schema tests, raw contract, doctor, safety checks, empty-account smoke | `make test` |
| Practical self-analytics answers | `yamusic_artist_affinity`, `yamusic_genre_periods`, `yamusic_track_signals`, `yamusic_playlist_signals`, `yamusic_library_profile`, dashboard genre/liked/search filters, dashboard Actions/Data Quality tabs, dashboard content smoke, `data/streamify_summary.md`, `data/streamify_snapshot.json`, `data/recommendations/*.csv` | `make product-answers-smoke`, `make dashboard-smoke`, `make report`, `make snapshot`, `make recommendations`, `make dashboard` |
| Empty/private account handling | typed empty raw files and empty dbt smoke | `scripts/smoke_empty_yamusic_dbt.py`, `make test` |
| Token safety | `.env.example`, `.gitignore`, no token in manifest/report/status, preflight without raw writes | `make status`, `make preflight`, `scripts/check_no_local_sensitive_artifacts.py` |

## Current Acceptance Status

Sample metadata path:

- `make acceptance-local` proves local ingestion, raw contract, DuckDB/dbt marts, doctor, report, readiness and dashboard startup.
- `make test` proves static contracts, safety guards, empty-account handling, sample acceptance, Python unit tests, Compose config and Compose local smoke.

Real account path:

- A valid `YANDEX_MUSIC_TOKEN` in `.env` is still required to prove real-account ingestion.
- The final real-account command is:

```bash
make acceptance-real
make dashboard
```

The readiness audit must report `"real_account_verified": true` before the real-account MVP is considered proven. `make acceptance-real` enforces this through `make readiness-real`, which runs `scripts/audit_yamusic_readiness.py --require-real`.

## Product Answers Covered

| User question | Primary artifact |
| --- | --- |
| Who are my strongest artists? | `yamusic_artist_affinity`, dashboard Artists tab |
| Which tracks repeat across library contexts? | `yamusic_track_signals.repeat_signal`, dashboard Tracks tab |
| How has genre composition shifted? | `yamusic_genre_periods`, dashboard Genres/Periods tabs |
| How diverse or concentrated is my library? | `yamusic_library_profile`, `yamusic_genre_profile` |
| Which playlists overlap? | `yamusic_playlist_overlap`, dashboard Playlists tab |
| Which tracks or playlists look underrated? | `yamusic_track_signals`, `yamusic_playlist_signals`, static report |
| What should I do next? | dashboard Actions tab, JSON snapshot `next_actions` |
| Can I open action queues in a spreadsheet? | `data/recommendations/*.csv`, `make recommendations` |
| Can I reuse the answers outside the dashboard? | `data/streamify_snapshot.json`, `make snapshot` |
| Is my local data trustworthy? | dashboard Data Quality tab, JSON snapshot quality block, `make doctor`, `make readiness` |

## Known Product Limits

- Yandex Music availability depends on the unofficial `yandex-music` package and account-visible metadata.
- Listening timestamps/history are used only when exposed by the account/API response; otherwise the product falls back to liked-track and playlist-membership events.
- The dashboard and report are analytics over metadata and derived events, not audio playback or audio feature extraction.
