# Streamify

Local-first music self-analytics for Yandex Music metadata, plus the original Kafka/Spark/Airflow/GCP streaming pipeline.

Streamify now has two compatible tracks:

- **Local product track**: ingest your Yandex Music metadata, build DuckDB/dbt marts, and open a Streamlit dashboard without cloud cost.
- **Legacy cloud engineering track**: keep the original Eventsim, Kafka, Spark Streaming, Airflow, dbt BigQuery and GCP architecture for portfolio-grade data engineering.

The local product track stores metadata and derived analytics only. It does not download or store audio.

## Local Yandex Music Self-Analytics

Product value: turn your own Yandex Music library into a reproducible local lakehouse that answers practical questions about your listening taste and library shape: favorite artists and tracks, genre shifts, playlist overlap, repeated patterns, diversity, active periods, underrated tracks and playlists, local data quality, and what data is missing.

First run without credentials:

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

Then open the Streamlit URL printed by `make dashboard`.

Run with your account metadata:

```bash
cp .env.example .env
make token-help
# Get a Yandex Music OAuth token with an external helper, then set YANDEX_MUSIC_TOKEN in .env.
make acceptance-real
make dashboard
```

Local defaults:

- command guide: `make help`
- token guide: `make token-help`
- raw metadata: `data/raw/yamusic/*.jsonl`
- local warehouse: `data/streamify.duckdb`
- local configuration: `.env` is loaded by the Python CLI/scripts and by `scripts/run_with_dotenv.py` for Makefile commands, so token and path overrides work without Make parsing token values.
- dbt target: `dbt build --profiles-dir . --target local --select yamusic`
- dbt packages: `make setup` and `make dbt-build` both run `dbt deps`, so a fresh checkout does not rely on ignored local `dbt/dbt_packages`.
- dbt local threads: `DBT_THREADS=1` by default for stable laptop/container runs; raise it explicitly if your environment is stable.
- local status: `make status` prints safe configuration/readiness hints without calling Yandex Music or printing token values.
- token preflight: `make preflight` checks real Yandex Music API access without writing raw data or printing the token.
- dashboard: `streamlit run dashboard/app.py`
- dashboard smoke: `make dashboard-smoke`
- static self-analytics report: `make report`, written to `data/streamify_summary.md`
- structured self-analytics snapshot: `make snapshot`, written to `data/streamify_snapshot.json` for automation and downstream agent workflows.
- spreadsheet action queues: `make recommendations`, written to `data/recommendations/*.csv` for rediscovery, playlist cleanup, standout playlists, top artists and genre shifts.
- static GitHub Pages site: `make pages-site`, generated into ignored `public/` from docs and safe sample/report artifacts.
- readiness audit: `make readiness`, which verifies raw counts, DuckDB marts, report, no audio artifacts and whether the latest run is sample or real Yandex Music metadata.
- local acceptance check: `make doctor`
- real-account acceptance: `make acceptance-real`, which also runs `make readiness-real` and fails unless the latest manifest source is `yandex_music`.
- safety guard: `scripts/check_no_local_sensitive_artifacts.py` keeps root `.env`, Yandex raw data, DuckDB files and local audio out of git.
- raw schema contract: `make raw-contract`
- Docker Compose smoke: `make compose-smoke-local`
- one-command container path: `make up-local`, which loads `.env` through `scripts/run_with_dotenv.py` and runs Docker Compose with the `local` profile. It uses real Yandex Music metadata when `YANDEX_MUSIC_TOKEN` is present in `.env`, otherwise it writes deterministic sample metadata.
- local reset: `make clean-local` removes generated raw metadata, DuckDB databases, summary/snapshot/recommendations reports, dbt target/logs/packages, and smoke-test artifacts while preserving `.env` and source files.

See [docs/yandex_music_local.md](docs/yandex_music_local.md) for the local architecture, token handling, and limitations. See [docs/yamusic_lineage.md](docs/yamusic_lineage.md) for raw-to-dashboard lineage and model ownership. See [docs/product_acceptance.md](docs/product_acceptance.md) for the requirement-to-command acceptance matrix.

GitHub delivery is managed through issue templates, a PR checklist, sample-data CI, GitHub Pages, and tag-based releases. See [docs/project_management.md](docs/project_management.md) and [docs/release_process.md](docs/release_process.md).

## Слой Качества Данных

Streamify нужен, чтобы построить потоковую аналитику музыкального сервиса: события из Kafka обрабатываются Spark Streaming, складываются в lake/warehouse, а dbt собирает таблицы для dashboard по прослушиваниям, пользователям, песням, артистам, локациям и времени.

В этой итерации добавлен проверяемый data-quality слой для core marts:

- добавлен dbt data-quality слой для core marts: `not_null`, `unique`, `relationships`, `accepted_values`;
- добавлены singular tests для SCD2 user dimension и orphan dimension keys в `fact_streams`;
- Airflow DAG теперь запускает `dbt build --select core --profiles-dir . --target prod`, а не только `dbt compile`;
- добавлена русская документация [docs/data_quality_checks.md](docs/data_quality_checks.md);
- добавлен CI/static validator `scripts/validate_dbt_quality.py` для проверки dbt quality contract без GCP credentials.

## Мой вклад в этом fork

Базовый проект уже содержит streaming pipeline и cloud setup. Мой добавленный слой отвечает за проверяемость аналитических core marts:

- перевел dbt core-модели с deprecated `dbt_utils.surrogate_key` на `dbt_utils.generate_surrogate_key`;
- обновил `dbt_utils` до версии `1.3.3` и зафиксировал package lock;
- добавил schema tests и singular tests для business-critical joins и SCD2-логики;
- усилил Airflow dbt DAG runtime path через `dbt deps` и `dbt build` с timeout-защитой;
- добавил статический CI gate, который проверяет dbt tests, Airflow DAG и документацию без GCP credentials.

Локальная проверка:

```bash
python3 scripts/validate_dbt_quality.py
python3 -m compileall -q airflow/dags spark_streaming scripts
cd airflow && GCP_PROJECT_ID=dummy GCP_GCS_BUCKET=dummy docker compose config --quiet
cd ../kafka && docker compose config --quiet
```

## Description

### Objective

The project will stream events generated from a fake music streaming service (like Spotify) and create a data pipeline that consumes the real-time data. The data coming in would be similar to an event of a user listening to a song, navigating on the website, authenticating. The data would be processed in real-time and stored to the data lake periodically (every two minutes). The hourly batch job will then consume this data, apply transformations, and create the desired tables for our dashboard to generate analytics. We will try to analyze metrics like popular songs, active users, user demographics etc.

### Dataset

[Eventsim](https://github.com/Interana/eventsim) is a program that generates event data to replicate page requests for a fake music web site. The results look like real use data, but are totally fake. The docker image is borrowed from [viirya's fork](https://github.com/viirya/eventsim) of it, as the original project has gone without maintenance for a few years now.

Eventsim uses song data from [Million Songs Dataset](http://millionsongdataset.com) to generate events. I have used a [subset](http://millionsongdataset.com/pages/getting-dataset/#subset) of 10000 songs.

### Tools & Technologies

- Cloud - [**Google Cloud Platform**](https://cloud.google.com)
- Infrastructure as Code software - [**Terraform**](https://www.terraform.io)
- Containerization - [**Docker**](https://www.docker.com), [**Docker Compose**](https://docs.docker.com/compose/)
- Stream Processing - [**Kafka**](https://kafka.apache.org), [**Spark Streaming**](https://spark.apache.org/docs/latest/streaming-programming-guide.html)
- Orchestration - [**Airflow**](https://airflow.apache.org)
- Transformation - [**dbt**](https://www.getdbt.com)
- Data Lake - [**Google Cloud Storage**](https://cloud.google.com/storage)
- Data Warehouse - [**BigQuery**](https://cloud.google.com/bigquery)
- Data Visualization - [**Data Studio**](https://datastudio.google.com/overview)
- Language - [**Python**](https://www.python.org)

### Architecture

![streamify-architecture](images/Streamify-Architecture.jpg)

### Final Result

![dashboard](images/dashboard.png)
## Setup

**WARNING: You will be charged for all the infra setup. You can avail 300$ in credit by creating a new account on GCP.**
### Pre-requisites

If you already have a Google Cloud account and a working terraform setup, you can skip the pre-requisite steps.

- Google Cloud Platform. 
  - [GCP Account and Access Setup](setup/gcp.md)
  - [gcloud alternate installation method - Windows](https://github.com/DataTalksClub/data-engineering-zoomcamp/blob/main/week_1_basics_n_setup/1_terraform_gcp/windows.md#google-cloud-sdk)
- Terraform
  - [Setup Terraform](https://github.com/DataTalksClub/data-engineering-zoomcamp/blob/main/week_1_basics_n_setup/1_terraform_gcp/windows.md#terraform)


### Get Going!

A video walkthrough of how I run my project - [YouTube Video](https://youtu.be/vzoYhI8KTlY)

- Procure infra on GCP with Terraform - [Setup](setup/terraform.md)
- (Extra) SSH into your VMs, Forward Ports - [Setup](setup/ssh.md)
- Setup Kafka Compute Instance and start sending messages from Eventsim - [Setup](setup/kafka.md)
- Setup Spark Cluster for stream processing - [Setup](setup/spark.md)
- Setup Airflow on Compute Instance to trigger the hourly data pipeline - [Setup](setup/airflow.md)


### Debug

If you run into issues, see if you find something in this debug [guide](setup/debug.md).
### How can I make this better?!
A lot can still be done :).
- Choose managed Infra
  - Cloud Composer for Airflow
  - Confluent Cloud for Kafka
- Create your own VPC network
- Build dimensions and facts incrementally instead of full refresh
- Create dimensional models for additional business processes
- Add more visualizations

### Special Mentions
I'd like to thank the [DataTalks.Club](https://datatalks.club) for offering this Data Engineering course for completely free. All the things I learnt there, enabled me to come up with this project. If you want to upskill on Data Engineering technologies, please check out the [course](https://github.com/DataTalksClub/data-engineering-zoomcamp). :)
