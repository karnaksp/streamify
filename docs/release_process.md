# Процесс релиза

Релизы Streamify публикуют исходный код и sample-артефакты, но не приватные данные. В публичные артефакты не должны попадать `.env`, real raw exports Яндекс Музыки, DuckDB-файлы, snapshots аккаунта, CSV-рекомендации реального аккаунта или audio.

## Чеклист релиза

1. Open or update GitHub issues for the agent lanes included in the release.
2. Run `make test` locally.
3. If ingestion changed, run `make acceptance-real` locally and keep the generated data untracked.
4. Confirm `git status --ignored .env data` shows `.env` and generated data as ignored.
5. Update `docs/releases/vX.Y.Z.md`.
6. Tag the release:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

Workflow `Release` прогоняет проверку на sample-данных, собирает публичную документацию, упаковывает tracked source через `git archive` и создает GitHub release из release notes.

## GitHub Pages

Workflow `GitHub Pages` собирает статический продуктовый сайт из README/docs и sample-отчета. Он намеренно очищает `YANDEX_MUSIC_TOKEN`, чтобы публичные страницы были воспроизводимыми и не зависели от приватного аккаунта.
