PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
VENV_DBT := $(VENV)/bin/dbt
VENV_STREAMLIT := $(VENV)/bin/streamlit
ENV_RUN := $(VENV_PYTHON) scripts/run_with_dotenv.py
DBT_PROFILES_DIR ?= dbt

.PHONY: help setup token-help status ingest ingest-sample preflight dbt-deps dbt-build dashboard dashboard-smoke doctor report snapshot recommendations readiness readiness-real real-gate-smoke product-answers-smoke pages-site acceptance-local acceptance-real compose-smoke-local compose-smoke-real test up-local compose-check clean-local

help:
	@printf '%s\n' 'Streamify local Yandex Music self-analytics'
	@printf '%s\n' ''
	@printf '%s\n' 'First local run with deterministic sample metadata:'
	@printf '%s\n' '  make setup'
	@printf '%s\n' '  make acceptance-local'
	@printf '%s\n' '  make dashboard'
	@printf '%s\n' ''
	@printf '%s\n' 'Real account run after setting YANDEX_MUSIC_TOKEN in .env:'
	@printf '%s\n' '  make token-help'
	@printf '%s\n' '  make status'
	@printf '%s\n' '  make acceptance-real'
	@printf '%s\n' '  make dashboard'
	@printf '%s\n' ''
	@printf '%s\n' 'Docker Compose local profile:'
	@printf '%s\n' '  make up-local'
	@printf '%s\n' '  make compose-smoke-local'
	@printf '%s\n' '  make compose-smoke-real    # requires YANDEX_MUSIC_TOKEN'
	@printf '%s\n' ''
	@printf '%s\n' 'Useful checks and exports:'
	@printf '%s\n' '  make raw-contract     Validate raw JSONL/manifest contracts'
	@printf '%s\n' '  make dbt-build        Build local DuckDB/dbt marts'
	@printf '%s\n' '  make report           Export markdown summary, JSON snapshot and CSV queues'
	@printf '%s\n' '  make pages-site       Build the static GitHub Pages site from safe local artifacts'
	@printf '%s\n' '  make readiness        Audit local product readiness'
	@printf '%s\n' '  make test             Run full local quality gate'
	@printf '%s\n' '  make clean-local      Remove generated local artifacts, preserve .env'

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt
	$(MAKE) dbt-deps

token-help:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/yamusic_token_help.py

status:
	$(ENV_RUN) -- $(VENV_PYTHON) -m yamusic_ingest --status

ingest:
	$(ENV_RUN) -- $(VENV_PYTHON) -m yamusic_ingest

ingest-sample:
	$(ENV_RUN) -- $(VENV_PYTHON) -m yamusic_ingest --sample

preflight:
	$(ENV_RUN) -- $(VENV_PYTHON) -m yamusic_ingest --preflight

dbt-deps:
	$(ENV_RUN) --cwd dbt -- $(abspath $(VENV_DBT)) deps

dbt-build: dbt-deps
	$(ENV_RUN) --cwd dbt -- $(abspath $(VENV_DBT)) build --profiles-dir . --target local --select yamusic

dashboard:
	$(ENV_RUN) -- $(VENV_STREAMLIT) run dashboard/app.py

dashboard-smoke:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_dashboard_content.py
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_dashboard.py

doctor:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/doctor_yamusic_local.py

report:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/export_yamusic_summary.py
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/export_yamusic_snapshot.py
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/export_yamusic_recommendations.py

snapshot:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/export_yamusic_snapshot.py

recommendations:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/export_yamusic_recommendations.py

readiness:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/audit_yamusic_readiness.py

readiness-real:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/audit_yamusic_readiness.py --require-real

real-gate-smoke:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_real_gate.py

product-answers-smoke:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_product_answers.py

pages-site:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/build_pages_site.py

raw-contract:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/validate_yamusic_raw_contract.py

acceptance-local: ingest-sample raw-contract dbt-build doctor report readiness dashboard-smoke

acceptance-real: preflight ingest raw-contract dbt-build doctor report readiness-real dashboard-smoke

compose-smoke-local:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_compose_local.py

compose-smoke-real:
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_compose_local.py --use-env-token

test:
	$(VENV_PYTHON) scripts/validate_yamusic_local.py
	$(VENV_PYTHON) scripts/check_no_local_sensitive_artifacts.py
	$(VENV_PYTHON) scripts/check_no_audio_artifacts.py
	$(ENV_RUN) -- $(VENV_PYTHON) scripts/smoke_empty_yamusic_dbt.py
	$(MAKE) acceptance-local
	$(MAKE) product-answers-smoke
	$(MAKE) real-gate-smoke
	$(MAKE) pages-site
	$(VENV_PYTHON) -m compileall -q scripts yamusic_ingest dashboard tests
	$(VENV_PYTHON) -m pytest -q
	$(ENV_RUN) -- docker compose -f docker-compose.local.yml config --quiet
	$(ENV_RUN) -- docker compose -f docker-compose.local.yml --profile local config --quiet
	$(MAKE) compose-smoke-local

up-local:
	$(ENV_RUN) -- docker compose -f docker-compose.local.yml --profile local up --build

compose-check:
	$(ENV_RUN) -- docker compose -f docker-compose.local.yml config --quiet
	$(ENV_RUN) -- docker compose -f docker-compose.local.yml --profile local config --quiet

clean-local:
	rm -rf data/raw/yamusic data/raw/yamusic_empty data/raw/yamusic_empty_smoke data/processed
	rm -rf data/streamify.duckdb data/streamify.duckdb.wal data/streamify_empty.duckdb data/streamify_empty.duckdb.wal
	rm -rf data/streamify_empty_smoke.duckdb data/streamify_empty_smoke.duckdb.wal data/streamify_summary.md data/streamify_snapshot.json data/recommendations
	rm -rf dbt/target dbt/logs dbt/dbt_packages
	rm -rf public
