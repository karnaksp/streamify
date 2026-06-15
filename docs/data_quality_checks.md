# Streamify Data Quality Checks

Streamify строит потоковую аналитику музыкального сервиса: Kafka принимает события, Spark Streaming пишет их в lake, Airflow запускает batch-слой, а dbt собирает core marts для dashboard. Этот документ фиксирует data-quality слой для dbt core marts и Airflow gate, который проверяет, что факты прослушиваний не теряют связи с измерениями.

## Что Проверяется

| Layer | Проверка | Зачем |
| --- | --- | --- |
| `fact_streams` | `not_null` и `relationships` для `userKey`, `artistKey`, `songKey`, `dateKey`, `locationKey` | Факт прослушивания не должен ссылаться на отсутствующие dimension rows. |
| `dim_users` | `unique`/`not_null` для `userKey`, `accepted_values` для `gender`, `level`, `currentRow` | SCD2 dimension должна сохранять валидные статусы пользователя. |
| `dim_songs`, `dim_artists`, `dim_location`, `dim_datetime` | `unique`/`not_null` для surrogate keys и обязательных атрибутов | Dashboard joins должны быть стабильными и воспроизводимыми. |
| `assert_dim_users_scd2_no_overlap.sql` | Нет пересекающихся SCD2 intervals и ровно одна current row на natural user key | История `free`/`paid` статусов не должна давать двойной матч факта. |
| `assert_fact_streams_no_orphan_keys.sql` | Нет orphan dimension keys после joins | Факт не должен терять семантику при построении wide view. |

## Airflow Flow

`airflow/dags/dbt_test_dag.py` теперь описывает DAG `dbt_quality_gate`:

1. `dbt_deps` устанавливает dbt packages.
2. `dbt_build_core` выполняет `dbt build --select core --profiles-dir . --target prod`.

`dbt build` важнее compile-only проверки: он запускает models и tests одним gate для production target.

## Локальная Проверка Без GCP Credentials

Полный `dbt build` требует BigQuery credentials. Для PR/CI без доступа к GCP добавлен static quality validator:

```bash
python3 scripts/validate_dbt_quality.py
python3 -m compileall -q airflow/dags spark_streaming
cd airflow && docker compose config
cd ../kafka && docker compose config
```

Эта проверка не заменяет runtime `dbt build`, но защищает инженерный контракт: модельные tests, singular tests, Airflow `dbt build` DAG и документация должны оставаться синхронизированными.
