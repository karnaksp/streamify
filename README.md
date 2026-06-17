# Streamify

Local-first self-analytics for your Yandex Music metadata.

Streamify turns a Yandex Music library into a reproducible local lakehouse: raw JSONL metadata, DuckDB/dbt marts, Streamlit dashboard, static summary, JSON snapshot, CSV action queues and GitHub Pages documentation. It stores metadata and derived analytics only. It does not download or store audio.

## Product Value

Streamify answers practical questions about a personal music library:

- which artists, tracks and genres dominate the library;
- how taste changes over months and release eras;
- which liked tracks are under-playlisted and worth rediscovering;
- which playlists overlap, stand out or need cleanup;
- how complete and fresh the local data is;
- what future location enrichment would need before map views can be trusted.

The current dashboard is chart-first: `Story`, `Taste Map`, `Atlas`, `Mix Shift`, `Rediscovery`, `Playlists`, `Explorer`, `Actions` and `Data Quality`.

## First Local Run

Run a deterministic local sample with no credentials:

```bash
cp .env.example .env
make setup
make acceptance-local
make dashboard
```

Then open the Streamlit URL printed by `make dashboard`.

Docker Compose uses the `local` profile, and `.env.example` pins `DBT_THREADS=1` for predictable laptop builds. Make targets load `.env` through `scripts/run_with_dotenv.py`, so secrets are passed through the process environment instead of Make parsing.

Run against your Yandex Music account:

```bash
cp .env.example .env
make token-help
# Put YANDEX_MUSIC_TOKEN into .env.
make acceptance-real
make dashboard
```

## Main Commands

```bash
make help                 # command map
make status               # safe local readiness/status hints
make token-help           # token setup guide, without printing secrets
make ingest               # real account metadata ingestion
make ingest-sample        # deterministic sample metadata
make raw-contract         # raw JSONL/manifest validation
make dbt-build            # local DuckDB/dbt marts
make report               # markdown summary, JSON snapshot, CSV queues
make snapshot             # JSON snapshot only
make recommendations      # CSV action queues only
make readiness-real       # require latest manifest source=yandex_music
make dashboard-smoke      # Streamlit content + HTTP smoke
make pages-site           # static GitHub Pages site in public/
make test                 # full local quality gate
make up-local             # Docker Compose local product profile
make compose-smoke-real   # Docker Compose smoke against a configured token
make clean-local          # remove generated local artifacts
```

## Local Artifacts

- Raw metadata: `data/raw/yamusic/*.jsonl`
- DuckDB warehouse: `data/streamify.duckdb`
- Markdown report: `data/streamify_summary.md`
- JSON snapshot: `data/streamify_snapshot.json`
- CSV action queues: `data/recommendations/*.csv`
- Optional enrichment inputs: `data/enrichment/*.csv`

All generated local artifacts are ignored by git. `.env` is ignored and must not be committed.

`make clean-local` removes generated raw data, reports, DuckDB files and dbt `target`/`logs`/`dbt_packages` artifacts without touching `.env`.

## Data Architecture

```text
Yandex Music metadata
  -> yamusic_ingest raw JSONL
  -> dbt staging views
  -> DuckDB marts
  -> Streamlit dashboard, reports, snapshots and recommendation queues
```

Core marts include:

- `yamusic_dim_tracks`, `yamusic_dim_artists`, `yamusic_dim_albums`, `yamusic_dim_playlists`
- `yamusic_fact_library_events`, `yamusic_fact_playlist_tracks`
- `yamusic_artist_affinity`, `yamusic_genre_profile`, `yamusic_genre_periods`
- `yamusic_track_signals`, `yamusic_playlist_signals`, `yamusic_playlist_overlap`
- `yamusic_library_profile`

See [docs/yamusic_lineage.md](docs/yamusic_lineage.md) for raw-to-dashboard lineage.

## Dashboard

The Streamlit dashboard focuses on evidence, not table dumps:

- `Story`: profile metrics, activity timeline and genre fingerprint.
- `Taste Map`: artist gravity and genre diversity.
- `Atlas`: genre atlas, monthly rhythm, music time travel, playlist subway, playlist DNA and Geo Atlas readiness.
- `Mix Shift`: genre heatmap, release-era mix and focus genre mix.
- `Rediscovery`: under-playlisted liked tracks and repeat quadrants.
- `Playlists`: playlist health and overlap.
- `Explorer`: filtered track cards and exact lookup.
- `Actions`: next steps and downloadable queues.
- `Data Quality`: source, raw counts, checksums and ingestion diagnostics.

## Optional Location Enrichment

Yandex Music metadata does not contain reliable listening location. Streamify therefore does not infer where listening happened from account region, playlist language, genre or artist origin.

Future map views require explicit local enrichment files under `data/enrichment`:

- `artist_locations.csv` for artist-associated places;
- `user_location_events.csv` for user-provided location timelines.

See [docs/location_enrichment.md](docs/location_enrichment.md) for schemas, source ideas, privacy constraints and timestamp join caveats.

## GitHub Pages

`make pages-site` builds a polished static product site into `public/`. The Pages workflow builds it from sample metadata with `YANDEX_MUSIC_TOKEN` empty, so public documentation is reproducible and does not depend on a private account.

The public site includes:

- product overview;
- local runbook;
- Atlas and location enrichment guidance;
- lineage;
- acceptance matrix;
- release process;
- generated sample summary when available.

## Quality Gates

`make test` runs the local product gate:

- repository contract validation;
- secret/audio artifact guards;
- empty/private account dbt smoke;
- sample acceptance flow;
- product-answer smoke;
- real-account gate smoke;
- Pages build;
- Python compile checks;
- pytest;
- Docker Compose config and local profile smoke.

`make acceptance-real` is the real account gate and fails unless the latest manifest proves `source=yandex_music`.

## Documentation

- [Local runbook](docs/yandex_music_local.md)
- [Lineage](docs/yamusic_lineage.md)
- [Product acceptance](docs/product_acceptance.md)
- [Location enrichment contract](docs/location_enrichment.md)
- [Project management](docs/project_management.md)
- [Release process](docs/release_process.md)
