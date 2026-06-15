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


def validate_schema_yml() -> None:
    schema = read("dbt/models/core/schema.yml")
    for model_name in [
        "fact_streams",
        "dim_users",
        "dim_songs",
        "dim_artists",
        "dim_location",
        "dim_datetime",
        "wide_streams",
    ]:
        if f"name: {model_name}" not in schema:
            raise AssertionError(f"schema.yml must document model {model_name}")

    for marker in [
        "relationships:",
        "accepted_values:",
        "field: userKey",
        "field: artistKey",
        "field: songKey",
        "field: dateKey",
        "field: locationKey",
        "values: ['free', 'paid']",
        "values: [0, 1]",
        "values: [true, false]",
    ]:
        if marker not in schema:
            raise AssertionError(f"schema.yml must contain {marker!r}")


def validate_singular_tests() -> None:
    require_markers(
        "dbt/tests/assert_dim_users_scd2_no_overlap.sql",
        [
            "overlapping_windows",
            "invalid_current_rows",
            "COUNTIF(currentRow = 1)",
            "HAVING current_row_count != 1",
        ],
    )
    require_markers(
        "dbt/tests/assert_fact_streams_no_orphan_keys.sql",
        [
            "LEFT JOIN {{ ref('dim_users') }}",
            "LEFT JOIN {{ ref('dim_artists') }}",
            "LEFT JOIN {{ ref('dim_songs') }}",
            "LEFT JOIN {{ ref('dim_datetime') }}",
            "LEFT JOIN {{ ref('dim_location') }}",
            "WHERE dim_users.userKey IS NULL",
        ],
    )


def validate_airflow_dag() -> None:
    require_markers(
        "airflow/dags/dbt_test_dag.py",
        [
            "dag_id='dbt_quality_gate'",
            "task_id=\"dbt_deps\"",
            "task_id=\"dbt_build_core\"",
            "dbt build --select core --profiles-dir . --target prod",
            "dbt_deps >> dbt_build_core",
        ],
    )


def validate_docs() -> None:
    require_markers(
        "README.md",
        [
            "## Слой Качества Данных",
            "Streamify нужен, чтобы построить потоковую аналитику музыкального сервиса",
            "docs/data_quality_checks.md",
            "scripts/validate_dbt_quality.py",
        ],
    )
    require_markers(
        "docs/data_quality_checks.md",
        [
            "потоковую аналитику музыкального сервиса",
            "fact_streams",
            "assert_dim_users_scd2_no_overlap.sql",
            "assert_fact_streams_no_orphan_keys.sql",
            "dbt_quality_gate",
            "python3 scripts/validate_dbt_quality.py",
        ],
    )


def main() -> int:
    validate_schema_yml()
    validate_singular_tests()
    validate_airflow_dag()
    validate_docs()
    print("OK: dbt quality checks, Airflow DAG and docs are aligned.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
