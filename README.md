# Streamify

Локальная self-analytics платформа для вашей Яндекс Музыки.

Streamify превращает музыкальную библиотеку в воспроизводимый локальный lakehouse: сырые JSONL-метаданные, DuckDB/dbt-марты, Streamlit dashboard, Markdown-отчет, JSON snapshot, CSV-очереди действий и GitHub Pages документацию. Проект хранит только метаданные и производные аналитические признаки. Аудио не скачивается, не сохраняется и не воспроизводится.

## Зачем Это Нужно

Streamify отвечает на прикладные вопросы о личной музыкальной библиотеке:

- какие артисты, треки и жанры реально доминируют;
- как меняется вкус по месяцам, эпохам релизов и жанровым периодам;
- какие любимые треки недопредставлены в плейлистах и стоят повторного открытия;
- какие плейлисты пересекаются, выделяются или требуют чистки;
- насколько полные, свежие и надежные локальные данные;
- какие данные нужны для будущих карт прослушивания без опасных догадок о геолокации.

Дашборд построен как продуктовый аналитический интерфейс, а не набор таблиц: `Story`, `Taste Map`, `Atlas`, `Mix Shift`, `Rediscovery`, `Playlists`, `Explorer`, `Actions`, `Data Quality`.

## Демонстрация Дашборда

Скриншоты ниже собираются из локального sample-прогона и не содержат приватных данных аккаунта.

![Обзор Streamify dashboard](docs/assets/dashboard-story.png)

![Atlas и визуальные инсайты](docs/assets/dashboard-atlas.png)

![Actions и очереди рекомендаций](docs/assets/dashboard-actions.png)

## Быстрый Локальный Запуск

Запуск на sample-данных без токена:

```bash
cp .env.example .env
make setup
make acceptance-local
make dashboard
```

После этого откройте URL, который напечатает `make dashboard`.

Docker Compose использует профиль `local`, а `.env.example` задает `DBT_THREADS=1`, чтобы сборка была предсказуемой на ноутбуке. Make-команды загружают `.env` через `scripts/run_with_dotenv.py`, поэтому секреты передаются через environment, а не парсятся Makefile.

Запуск на вашей Яндекс Музыке:

```bash
cp .env.example .env
make token-help
# Добавьте YANDEX_MUSIC_TOKEN в .env.
make acceptance-real
make dashboard
```

`make acceptance-real` падает, если последний manifest не доказывает `source=yandex_music`.

## Основные Команды

```bash
make help                 # карта команд
make status               # безопасная диагностика локального состояния
make token-help           # подсказка по токену без печати секретов
make ingest               # ingestion метаданных реального аккаунта
make ingest-sample        # детерминированные sample-данные
make raw-contract         # проверка raw JSONL и manifest
make dbt-build            # локальные DuckDB/dbt-марты
make report               # Markdown summary, JSON snapshot, CSV queues
make snapshot             # только JSON snapshot
make recommendations      # только CSV action queues
make readiness-real       # требовать source=yandex_music
make dashboard-smoke      # Streamlit content + HTTP smoke
make pages-site           # статический GitHub Pages сайт в public/
make test                 # полный локальный quality gate
make up-local             # Docker Compose local product profile
make compose-smoke-real   # Docker Compose smoke с настроенным токеном
make clean-local          # удалить локально сгенерированные артефакты
```

## Локальные Артефакты

- Raw metadata: `data/raw/yamusic/*.jsonl`
- DuckDB warehouse: `data/streamify.duckdb`
- Markdown report: `data/streamify_summary.md`
- JSON snapshot: `data/streamify_snapshot.json`
- CSV action queues: `data/recommendations/*.csv`
- Optional enrichment inputs: `data/enrichment/*.csv`

Все локально сгенерированные артефакты игнорируются git. `.env` тоже игнорируется и не должен попадать в коммиты.

`make clean-local` удаляет raw data, отчеты, DuckDB-файлы и dbt `target`/`logs`/`dbt_packages`, но не трогает `.env`.

## Архитектура Данных

```text
Метаданные Яндекс Музыки
  -> yamusic_ingest raw JSONL
  -> dbt staging views
  -> DuckDB marts
  -> Streamlit dashboard, reports, snapshots, recommendation queues
```

Ключевые марты:

- `yamusic_dim_tracks`, `yamusic_dim_artists`, `yamusic_dim_albums`, `yamusic_dim_playlists`
- `yamusic_fact_library_events`, `yamusic_fact_playlist_tracks`
- `yamusic_artist_affinity`, `yamusic_genre_profile`, `yamusic_genre_periods`
- `yamusic_track_signals`, `yamusic_playlist_signals`, `yamusic_playlist_overlap`
- `yamusic_library_profile`

Lineage описан в [docs/yamusic_lineage.md](docs/yamusic_lineage.md).

## Что Показывает Дашборд

- `Story`: профиль библиотеки, timeline активности и жанровый отпечаток.
- `Taste Map`: гравитация артистов и разнообразие жанров.
- `Atlas`: genre atlas, monthly rhythm, music time travel, playlist subway, playlist DNA и Geo Atlas readiness.
- `Mix Shift`: жанровая heatmap, release-era mix и focus genre mix.
- `Rediscovery`: любимые треки, которые мало представлены в плейлистах.
- `Playlists`: здоровье плейлистов и overlap.
- `Explorer`: фильтруемые карточки треков и точечный поиск.
- `Actions`: следующие действия и downloadable queues.
- `Data Quality`: source, raw counts, checksums и ingestion diagnostics.

## География И Карты

Метаданные Яндекс Музыки не содержат надежную геолокацию прослушивания. Streamify не делает вид, что регион аккаунта, язык плейлиста, жанр или происхождение артиста равны вашему местоположению.

Будущие карты требуют явных локальных enrichment-файлов в `data/enrichment`:

- `artist_locations.csv`: места, связанные с артистами;
- `user_location_events.csv`: пользовательская timeline геолокации.

Схемы, источники и privacy-ограничения описаны в [docs/location_enrichment.md](docs/location_enrichment.md).

## GitHub Pages

`make pages-site` собирает современный русскоязычный статический сайт в `public/`. Workflow Pages строит его на sample metadata с пустым `YANDEX_MUSIC_TOKEN`, поэтому публичная документация воспроизводима и не зависит от приватного аккаунта.

Публичный сайт включает:

- продуктовый overview;
- локальный runbook;
- демонстрации dashboard;
- Atlas и location enrichment;
- lineage;
- acceptance matrix;
- release process;
- generated sample summary, если он доступен.

## Quality Gates

`make test` запускает локальный product gate:

- repository contract validation;
- secret/audio artifact guards;
- empty/private account dbt smoke;
- sample acceptance flow;
- product-answer smoke;
- real-account gate smoke;
- Pages build;
- Python compile checks;
- pytest;
- Docker Compose config и local profile smoke.

## Документация

- [Локальный runbook](docs/yandex_music_local.md)
- [Lineage](docs/yamusic_lineage.md)
- [Product acceptance](docs/product_acceptance.md)
- [Location enrichment contract](docs/location_enrichment.md)
- [Project management](docs/project_management.md)
- [Release process](docs/release_process.md)
