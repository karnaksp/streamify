# Контракт гео-обогащения

Этот документ описывает будущий опциональный слой геоданных для Streamify. Он не входит в текущий ingestion Яндекс Музыки и не должен восприниматься как уже реализованная функция.

## Почему метаданных Яндекс Музыки недостаточно

Текущий адаптер Яндекс Музыки читает доступные аккаунту метаданные через Python-клиент `yandex-music`: треки, артистов, альбомы, плейлисты, состав плейлистов, лайки и производные события библиотеки. В этих данных нет надежного поля с местом прослушивания.

Даже если timestamp присутствует, он описывает действие в библиотеке: лайк, добавление в плейлист или доступный аккаунту элемент истории. Он не доказывает, где пользователь находился во время прослушивания. Регион аккаунта, доступность каталога, язык плейлиста, страна артиста или жанр не являются сигналами местоположения пользователя.

## Безопасные источники местоположения

Гео-обогащение должно быть явным, опциональным и отделенным от музыкального ingestion. Возможные источники:

- Google Timeline / Google Takeout Location History, если хронология включена и пользователь явно экспортирует данные.
- GPS в EXIF фотографий, только из выбранных пользователем фото и только с явным согласием.
- Экспорты календаря и поездок: перелеты, отели, мероприятия, билеты.
- Ручная city timeline, например интервалы `2025-06-01` - `2025-06-14` в `Tbilisi, Georgia`.
- Сетевые или IP-логи только если пользователь сам их предоставляет и понимает ограничения точности.
- iOS Significant Locations можно считать потенциальным on-device источником, но он плохо подходит для надежного экспорта в Streamify.

Что нельзя считать безопасным источником по умолчанию:

- выводить местоположение пользователя из страны артиста, языка трека, жанра, названия плейлиста или региона аккаунта;
- собирать location из устройства, браузера или сети без отдельного шага импорта;
- считать грубую IP-геолокацию точной историей перемещений.

## `user_location_events`

`user_location_events` should represent where the user may have been during a time interval, with confidence and provenance.

Рекомендуемые поля:

| Поле | Тип | Примечания |
| --- | --- | --- |
| `location_event_id` | string | Stable hash of source, source row id and normalized time interval. |
| `source` | string | `google_takeout`, `photo_exif`, `calendar_travel`, `manual_city_timeline`, `network_ip_log`, or another explicit import source. |
| `source_record_id` | string | Optional source-local identifier, redacted where needed. |
| `started_at` | timestamp | Inclusive UTC start time. |
| `ended_at` | timestamp | Exclusive UTC end time; may equal `started_at` for point observations. |
| `timezone` | string | IANA timezone when known. |
| `latitude` | double | Optional; omit or round when only coarse location is needed. |
| `longitude` | double | Optional; omit or round when only coarse location is needed. |
| `city` | string | Optional normalized city. |
| `region` | string | Optional state/province/region. |
| `country_code` | string | Optional ISO 3166-1 alpha-2 code. |
| `precision_meters` | integer | Approximate spatial precision or bucket size. |
| `confidence` | double | `0.0` to `1.0`; manual ranges and IP-derived locations should usually be lower confidence than direct GPS. |
| `is_inferred` | boolean | True when the row is inferred from an indirect source such as calendar travel or IP logs. |
| `consent_scope` | string | User-approved scope, such as `analytics_only` or `city_level_only`. |
| `imported_at` | timestamp | Time Streamify imported the row. |

The table should allow overlapping rows because real-world sources conflict. Downstream joins must choose a deterministic tie-break rule instead of assuming one location per timestamp.

## `artist_locations`

`artist_locations` описывает места, связанные с артистами, а не места прослушивания пользователя. Таблица может отвечать на вопросы о географическом разнообразии артистов, но не должна использоваться как доказательство того, где пользователь слушал музыку.

Рекомендуемые поля:

| Поле | Тип | Примечания |
| --- | --- | --- |
| `artist_location_id` | string | Stable hash of artist id, source and normalized location. |
| `artist_id` | string | Streamify/Yandex artist identifier when available. |
| `artist_name` | string | Display name for review and fallback matching. |
| `source` | string | Discogs, MusicBrainz, Wikidata, manual curation or another cited source. |
| `source_url` | string | Optional provenance URL. |
| `location_type` | string | `origin`, `formed_in`, `based_in`, `birthplace`, `scene`, or `label_location`. |
| `started_at` | date | Optional date when the association began. |
| `ended_at` | date | Optional date when the association ended. |
| `city` | string | Optional normalized city. |
| `region` | string | Optional region. |
| `country_code` | string | Optional ISO 3166-1 alpha-2 code. |
| `latitude` | double | Optional coarse coordinate for mapping. |
| `longitude` | double | Optional coarse coordinate for mapping. |
| `confidence` | double | `0.0` to `1.0`; biographies and crowd-sourced sources require care. |
| `notes` | string | Optional caveat for ambiguous or multi-location artists. |

## Join геоданных с музыкальными событиями

The future join should be timestamp-based and explicit about uncertainty:

1. Normalize all `user_library_events.event_at`, `user_location_events.started_at` and `user_location_events.ended_at` values to UTC.
2. For each library event with a usable timestamp, find location events where `started_at <= event_at < ended_at`.
3. If no interval matches, optionally search nearest point observations within a configured window, such as 30 minutes for GPS-like data or one day for manual city timelines.
4. Rank candidates by source trust, precision, confidence, non-inferred status and distance from the observation time.
5. Persist the selected match in a bridge table such as `user_library_event_locations`, including `location_event_id`, `match_method`, `match_confidence`, `time_delta_seconds` and `location_precision_meters`.
6. Keep unmatched music events. Missing location is expected and should not fail ingestion.

Recommended bridge fields:

| Field | Type | Notes |
| --- | --- | --- |
| `event_location_id` | string | Stable hash of library event and selected location event. |
| `library_event_id` | string | Existing music/library event id. |
| `location_event_id` | string | Selected user location event id. |
| `match_method` | string | `interval_exact`, `nearest_point`, `manual_range`, `calendar_range`, `ip_coarse`, or similar. |
| `match_confidence` | double | Combined confidence after tie-breaking. |
| `time_delta_seconds` | integer | `0` for interval matches; signed delta for nearest-point matches. |
| `location_precision_meters` | integer | Spatial precision used for the match. |

## Privacy Constraints

- Location imports must be opt-in and separate from `YANDEX_MUSIC_TOKEN` setup.
- Raw high-precision location files should remain local, ignored by git and excluded from reports by default.
- Default analytics should use city, region or country buckets instead of exact coordinates.
- Users must be able to delete imported location data without deleting music metadata.
- Reports, snapshots and dashboards should label location-derived metrics as optional and source-dependent.
- The manifest should store row counts, source names and checksums, not raw coordinates or sensitive source identifiers.
- Consent scope should travel with derived rows so a city-only import is not later used for exact maps.
- IP-derived rows must be marked inferred and coarse, and must never be collected implicitly.

## Inference Caveats

Location enrichment can answer "what music-library event happened while the user's provided location data suggests they were in this place?" It cannot prove the user listened there unless the source event itself is a trustworthy listening event and the location source is accurate for the same time.

Important caveats:

- Library likes and playlist edits can happen long after listening.
- Manual city timelines are useful for coarse trip context but poor for exact movement.
- Calendar travel can describe intended plans, not actual presence.
- GPS and photo EXIF can be sparse and biased toward moments when photos were taken.
- IP geolocation can be wrong because of VPNs, mobile carriers, corporate networks and provider databases.
- Artist location is artist metadata, not user location.

Any product surface using this contract should show confidence and source labels, avoid precise claims, and prefer language such as "associated with your provided location timeline" over "listened in."
