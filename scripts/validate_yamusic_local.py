#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    file_path = ROOT / path
    if not file_path.exists():
        raise AssertionError(f"Missing required file: {path}")
    return file_path.read_text(encoding="utf-8")


def require_markers(path: str, markers: list[str]) -> None:
    text = read(path)
    for marker in markers:
        if marker not in text:
            raise AssertionError(f"{path} must contain {marker!r}")


def reject_markers(path: str, markers: list[str]) -> None:
    text = read(path)
    for marker in markers:
        if marker in text:
            raise AssertionError(f"{path} must not contain {marker!r}")


def main() -> int:
    for path in [
        "yamusic_ingest/__main__.py",
        "yamusic_ingest/yandex_client.py",
        "dashboard/app.py",
        "dashboard/actions.py",
        "docker-compose.local.yml",
        "Makefile",
        ".github/workflows/data-quality.yml",
        ".env.example",
        "docs/yamusic_lineage.md",
        "docs/product_acceptance.md",
        "docs/location_enrichment.md",
        "dbt/README.md",
        "dbt/models/yamusic/schema.yml",
        "dbt/tests/assert_yamusic_playlist_tracks_no_orphan_keys.sql",
        "dbt/tests/assert_yamusic_library_events_no_orphan_keys.sql",
        "scripts/check_no_local_sensitive_artifacts.py",
        "scripts/check_no_audio_artifacts.py",
        "scripts/validate_yamusic_raw_contract.py",
        "scripts/smoke_empty_yamusic_dbt.py",
        "scripts/smoke_dashboard.py",
        "scripts/smoke_dashboard_content.py",
        "scripts/smoke_compose_local.py",
        "scripts/smoke_real_gate.py",
        "scripts/smoke_product_answers.py",
        "scripts/run_with_dotenv.py",
        "scripts/doctor_yamusic_local.py",
        "scripts/export_yamusic_summary.py",
        "scripts/export_yamusic_snapshot.py",
        "scripts/export_yamusic_recommendations.py",
        "scripts/audit_yamusic_readiness.py",
        "scripts/build_pages_site.py",
        "scripts/yamusic_token_help.py",
        ".github/workflows/pages.yml",
        ".github/workflows/release.yml",
        ".github/ISSUE_TEMPLATE/agent_task.yml",
        ".github/ISSUE_TEMPLATE/data_quality.yml",
        ".github/ISSUE_TEMPLATE/product_request.yml",
        ".github/PULL_REQUEST_TEMPLATE.md",
        "docs/project_management.md",
        "docs/release_process.md",
        "docs/releases/v0.1.0.md",
    ]:
        if not (ROOT / path).exists():
            raise AssertionError(f"Missing required local product file: {path}")

    for path in [
        "eventsim",
        "kafka",
        "spark_streaming",
        "airflow",
        "terraform",
        "setup",
        "images",
        "dbt/models/core",
        "dbt/seeds",
        "scripts/validate_dbt_quality.py",
        "scripts/eventsim_startup.sh",
        "scripts/airflow_startup.sh",
        "scripts/spark_setup.sh",
        "scripts/vm_setup.sh",
    ]:
        if (ROOT / path).exists():
            raise AssertionError(f"Legacy demo artifact must be removed: {path}")

    legacy_markers = [
        "Eventsim",
        "GCP",
        "BigQuery",
        "Kafka",
        "Spark",
        "Airflow",
        "Terraform",
        "DataTalks",
        "validate_dbt_quality",
        "spark_streaming",
        "eventsim",
        "dbt-bigquery",
        "kafka-python",
        "fact_streams",
        "dim_users",
    ]
    for path in [
        "README.md",
        "docs/yandex_music_local.md",
        "docs/product_acceptance.md",
        "docs/release_process.md",
        "dbt/README.md",
        "dbt/dbt_project.yml",
        "dbt/profiles.yml",
        "docker-compose.local.yml",
        "Makefile",
        "requirements.txt",
        "scripts/build_pages_site.py",
        "scripts/smoke_empty_yamusic_dbt.py",
    ]:
        reject_markers(path, legacy_markers)

    require_markers(
        "README.md",
        ["Яндекс Музыки", "DuckDB", "make help", "make status", "make ingest-sample", "make acceptance-real", "make dashboard", "как меняется вкус", "`local`", "DBT_THREADS=1", "scripts/run_with_dotenv.py", "make clean-local", "dbt `target`/`logs`/`dbt_packages`", "make readiness-real", "make up-local", "make compose-smoke-real", "make snapshot", "make recommendations", "make pages-site", "GitHub Pages", "streamify_snapshot.json", "data/recommendations", "География и карты", "Atlas", "docs/assets/dashboard-story.png", "docs/assets/dashboard-atlas.png", "docs/assets/dashboard-actions.png"],
    )
    require_markers(
        "docs/yandex_music_local.md",
        ["YANDEX_MUSIC_TOKEN", "make acceptance-real", "make status", "make token-help", "make compose-smoke-real", "built-in device auth", "bounded retries", "dbt build --profiles-dir . --target local", "не скачивает", "underrated tracks", "Проверка реального аккаунта", "Empty/private accounts", "scripts/run_with_dotenv.py", "make dbt-build", "make up-local", "streamify_empty_smoke", "--require-real", "stale Parquet cleanup", "JSONL sha256 checksums", "ingestion diagnostics", "ingestion diagnostics consistency", "STREAMIFY_SNAPSHOT_PATH", "STREAMIFY_RECOMMENDATIONS_DIR", "streamify_snapshot.json", "data/recommendations", "latest manifest source", "Actions tab"],
    )
    require_markers(
        "docs/yamusic_lineage.md",
        ["Raw/Bronze", "Silver", "Gold", "liked albums", "liked artists", "liked playlists", "stg_yamusic_manifest", "adapter/client metadata", "diagnostics counters", "JSONL sha256 checksums", "ingestion diagnostics consistency", "yamusic_genre_periods", "Продуктовые вопросы", "Quality gates", "make acceptance-real", "referential integrity", "Snapshot export", "JSON snapshot", "Recommendations export"],
    )
    require_markers(
        "docs/product_acceptance.md",
        ["Матрица требований", "make acceptance-local", "make test", "make acceptance-real", "real_account_verified", "No audio", "Yandex Music metadata ingestion", "make readiness-real", "make compose-smoke-real", "make product-answers-smoke", "stale Parquet cleanup", "Source provenance", "data/streamify_snapshot.json", "make snapshot", "data/recommendations/*.csv", "make recommendations", "dashboard Actions tab"],
    )
    require_markers("dbt/profiles.yml", ["type: duckdb", "target: local", "DBT_THREADS"])
    require_markers("dbt/README.md", ["dbt-модели Streamify", "self-analytics Яндекс Музыки", "staging/stg_yamusic_*", "marts/yamusic_dim_*", "data/streamify.duckdb"])
    require_markers(".env.example", ["YANDEX_MUSIC_TOKEN=", "STREAMIFY_REPORT_PATH", "STREAMIFY_SNAPSHOT_PATH", "STREAMIFY_RECOMMENDATIONS_DIR", "STREAMIFY_ENRICHMENT_DIR", "DBT_THREADS=1"])
    require_markers(
        "dbt/models/yamusic/schema.yml",
        ["stg_yamusic_tracks", "stg_yamusic_manifest", "manifest_source", "adapter_name", "client_library", "yamusic_artist_affinity", "yamusic_library_profile", "yamusic_period_activity", "yamusic_genre_periods", "yamusic_track_signals", "yamusic_playlist_signals", "stale_ingestion_flag", "diagnostic_liked_shortcuts_fetch_failed", "diagnostic_liked_tracks_duplicate_skipped", "diagnostic_liked_albums_seen", "diagnostic_liked_artists_seen", "diagnostic_liked_playlists_seen", "diagnostic_playlist_tracks_fetch_failed", "diagnostic_playlist_tracks_missing_track_id", "diagnostic_playlist_tracks_duplicate_skipped", "raw_tracks_sha256", "raw_user_library_events_sha256"],
    )
    require_markers("dashboard/app.py", ["Local DuckDB database is missing", "Streamify Self-Analytics", "Streamify Taste Console", "Focus controls", "Quick lens", "Story", "Taste Map", "Atlas", "Mix Shift", "Rediscovery", "Activity timeline", "Genre fingerprint", "Artist gravity", "Genre diversity", "Genre Atlas", "Monthly Rhythm", "Music Time Travel", "Playlist Subway", "Playlist DNA", "Geo Atlas readiness", "artist_locations.csv", "user_location_events.csv", "Genre heatmap", "Release-era mix", "Playlist health", "Playlist overlap", "Actions", "Next actions", "Action previews", "Rediscovery queue", "Rediscovery quadrants", "Playlist cleanup candidates", "Download snapshot", "Download action queues", "RECOMMENDATIONS_DIR", "ENRICHMENT_DIR", "No Yandex Music library metadata was returned", "manifest_source", "adapter_name", "raw_counts", "raw_checksums", "ingestion_diagnostics", "build_data_next_actions", "apply_focus_filters", "apply_track_filters", "st.sidebar.radio", "st.sidebar.multiselect", "st.sidebar.selectbox", "st.sidebar.text_input", "st.sidebar.slider"])
    require_markers("dashboard/actions.py", ["build_data_next_actions", "YANDEX_MUSIC_TOKEN", "stale_ingestion_flag", "liked shortcuts failed", "playlist shortcuts failed", "Data is ready for exploration"])
    require_markers("docker-compose.local.yml", ['profiles: ["local"]', "YANDEX_MUSIC_TOKEN", "service_completed_successfully", "DBT_THREADS", "set -euo pipefail", "READINESS_ARGS", "--require-real", "validate_yamusic_raw_contract.py", "doctor_yamusic_local.py", "export_yamusic_summary.py", "export_yamusic_snapshot.py", "export_yamusic_recommendations.py", "audit_yamusic_readiness.py"])
    require_markers("Makefile", ["help:", "token-help:", "yamusic_token_help.py", "pages-site:", "Streamify local Yandex Music self-analytics", "scripts/run_with_dotenv.py", "$(ENV_RUN) -- docker compose -f docker-compose.local.yml --profile local up --build", "$(ENV_RUN) -- docker compose -f docker-compose.local.yml --profile local config --quiet", "dbt-build: dbt-deps", "status", "preflight", "dashboard-smoke", "compose-smoke-local", "compose-smoke-real", "acceptance-real", "raw-contract", "report", "snapshot", "recommendations", "readiness", "readiness-real", "real-gate-smoke", "product-answers-smoke", "check_no_local_sensitive_artifacts.py", "check_no_audio_artifacts.py", "smoke_empty_yamusic_dbt.py", "smoke_real_gate.py", "smoke_product_answers.py", "smoke_dashboard_content.py", "acceptance-local", "doctor_yamusic_local.py", "streamify_empty", "dbt/dbt_packages", "streamify_snapshot.json", "data/recommendations", "build_pages_site.py"])
    reject_markers("Makefile", ["include .env"])
    require_markers("scripts/run_with_dotenv.py", ["load_dotenv", "os.execvpe", "--cwd", "Make parsing secrets"])
    require_markers(".github/workflows/data-quality.yml", ["make test", "YANDEX_MUSIC_TOKEN", "DBT_THREADS"])
    require_markers(".github/workflows/pages.yml", ["GitHub Pages", "make acceptance-local", "build_pages_site.py", "YANDEX_MUSIC_TOKEN: \"\"", "actions/deploy-pages"])
    require_markers(".github/workflows/release.yml", ["Release", "tags:", "make test", "git archive", "gh release create"])
    require_markers(".github/ISSUE_TEMPLATE/agent_task.yml", ["Направление", "Repo/Build", "Yandex Ingestion", "Analytics/dbt", "Product/Dashboard", "QA/Integration"])
    require_markers(".github/PULL_REQUEST_TEMPLATE.md", ["Продуктовая ценность", "Влияние на данные", "make test", "make acceptance-real"])
    require_markers("docs/project_management.md", ["Направления агентов", "Repo/Build", "Yandex Ingestion", "QA/Integration", "v0.1.0-local-mvp"])
    require_markers("docs/release_process.md", ["Чеклист релиза", "GitHub Pages", "sample-данных", "git tag vX.Y.Z"])
    require_markers("scripts/build_pages_site.py", ["PUBLIC_DIR", "Главная", "Дашборд", "Atlas + Гео", "streamify_summary.md", "dashboard.html", "location.html", "hero-visual", "side-link", "media-frame", "inline_markdown", "docs/assets/", "assets/", "index.html"])
    require_markers("scripts/yamusic_token_help.py", ["TOKEN_HELPER_URL", "supports_device_auth", "token_configured", "make preflight", "make acceptance-real"])
    require_markers("scripts/check_no_local_sensitive_artifacts.py", ["FORBIDDEN_TRACKED_PATHS", "data/raw/yamusic", "DuckDB files", "audio artifacts are tracked"])
    require_markers("scripts/check_no_audio_artifacts.py", ["AUDIO_EXTENSIONS", "must not store audio files"])
    require_markers("scripts/validate_yamusic_raw_contract.py", ["SCHEMAS", "DIAGNOSTIC_FIELDS", "validate_diagnostic_consistency", "jsonl_sha256", "sha256 mismatch", "playlist_tracks_written", "playlist_tracks_fetch_failed", "liked_tracks_duplicate_skipped", "liked_playlists_written", "playlist_tracks_duplicate_skipped", "liked shortcut diagnostics must add up", "Yandex Music raw schema contract is valid", "user_library_events", "adapter_name", "client_library"])
    require_markers("scripts/smoke_empty_yamusic_dbt.py", ["yamusic_empty_smoke", "--no-partial-parse", "dbt.cli.main", "deps_command", "empty Yandex Music raw datasets", "stale_ingestion_flag", "jsonl_sha256"])
    require_markers("scripts/smoke_dashboard.py", ["dashboard returned HTTP 200", "STREAMIFY_DUCKDB_PATH", "server.headless=true"])
    require_markers("scripts/smoke_dashboard_content.py", ["AppTest", "Story", "Taste Map", "Atlas", "Mix Shift", "Rediscovery", "Data Quality", "Geo Atlas readiness", "dashboard content exposes the expected self-analytics sections"])
    require_markers("scripts/smoke_compose_local.py", ["--use-env-token", "docker compose local profile returned HTTP 200", "produced valid local product artifacts", "YANDEX_MUSIC_TOKEN", "wait_for_http", "assert_no_runtime_failures", "run_host_check", "validate_yamusic_raw_contract.py", "--require-real", "smoke_product_answers.py", "smoke_dashboard_content.py", "ModuleNotFoundError"])
    require_markers("scripts/smoke_real_gate.py", ["sample metadata is rejected", "--require-real", "source=yandex_music", "YANDEX_MUSIC_TOKEN"])
    require_markers("scripts/smoke_product_answers.py", ["favorite artists", "repeat signals", "genre shifts", "playlist overlap", "Data Quality", "manifest_source", "adapter_name", "Raw Ingestion Counts", "Raw File Checksums", "raw_checksums", "diagnostic_liked_shortcuts_seen", "JSON snapshot", "streamify_snapshot.json", "recommendations export", "rediscovery_tracks.csv"])
    require_markers("scripts/doctor_yamusic_local.py", ["_manifest.json", "stg_yamusic_manifest", "adapter metadata", "yamusic_genre_periods", "raw counts", "local Yandex Music acceptance checks passed"])
    require_markers("scripts/export_yamusic_summary.py", ["Streamify Yandex Music Self-Analytics Summary", "STREAMIFY_REPORT_PATH", "yamusic_artist_affinity", "yamusic_playlist_signals", "Raw Ingestion Counts", "Raw File Checksums", "Ingestion Diagnostics", "Adapter version"])
    require_markers("scripts/export_yamusic_snapshot.py", ["Streamify Yandex Music Self-Analytics", "STREAMIFY_SNAPSHOT_PATH", "schema_version", "favorite_artists", "playlist_overlap", "raw_checksums", "ingestion_diagnostics"])
    require_markers("scripts/export_yamusic_recommendations.py", ["STREAMIFY_RECOMMENDATIONS_DIR", "rediscovery_tracks.csv", "playlist_cleanup.csv", "standout_playlists.csv", "genre_shifts.csv"])
    require_markers("scripts/audit_yamusic_readiness.py", ["real_account_verified", "local product readiness", "Audio files must not be stored", "yamusic_library_profile", "manifest_source", "adapter_name", "raw_checksums_from_profile", "ingestion_diagnostics", "snapshot_path", "recommendations_dir", "--require-real", "source=yandex_music"])
    require_markers("yamusic_ingest/config.py", ["def load_dotenv", "export ", "os.environ.setdefault"])
    require_markers("yamusic_ingest/yandex_client.py", ["IngestResult", "_call_with_retries", "sleep", "failed after", "client.users_likes_tracks", "client.users_likes_playlists", "shortcut.fetch_track"])
    require_markers("yamusic_ingest/__main__.py", ["DIAGNOSTIC_FIELDS", "liked_albums_seen", "liked_artists_seen", "liked_playlists_seen", "jsonl_sha256", "--status", "token_configured", "last_source", "manifest_read_error", "snapshot_exists", "recommendations_exists", "next_step", "make preflight", "make acceptance-real", "client_metadata"])
    require_markers("yamusic_ingest/io.py", ["file_sha256", "remove_file_if_exists", "write_parquet_if_available"])
    print("OK: local Yandex Music product contract is aligned.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
