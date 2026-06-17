# Управление проектом Streamify

Работа по Streamify ведется через задачи размером под одного агента. В каждой задаче должны быть продуктовый результат, ответственное направление и конкретные доказательства готовности.

## Направления агентов

| Направление | Зона ответственности | Проверка по умолчанию |
| --- | --- | --- |
| Repo/Build | Local setup, Docker Compose, Makefile, CI, release automation | `make test`, `make compose-smoke-local` |
| Yandex Ingestion | Token-safe metadata ingestion, raw contracts, API edge cases | `make preflight`, `make ingest`, `make raw-contract` |
| Analytics/dbt | DuckDB targets, typed staging, marts, tests, lineage | `make dbt-build`, `make doctor` |
| Product/Dashboard | Streamlit UX, exports, product docs, answer quality | `make dashboard-smoke`, `make product-answers-smoke` |
| QA/Integration | End-to-end acceptance, privacy gates, release readiness | `make acceptance-local`, `make acceptance-real` |

## Правила работы

- Do not paste tokens, raw account data, DuckDB files, or screenshots with private listening data into issues.
- Use sample metadata for CI, GitHub Pages, and public release artifacts.
- Use `make acceptance-real` only on a trusted local machine with `.env`.
- Every PR should update tests or explain why the existing gates prove the change.
- Release candidates should link the GitHub issue set they close and include known API limitations.

## План релизов

1. `v0.1.0-local-mvp`: real-account metadata ingestion, DuckDB marts, dashboard, safety gates.
2. `v0.2.0-product-answers`: richer action queues, more dashboard filters, better empty/error states.
3. `v0.3.0-official-import`: optional official Yandex data archive importer if usable account export data is available.
