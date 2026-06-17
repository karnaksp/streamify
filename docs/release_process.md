# Release Process

Streamify releases are source-first and privacy-safe. Public artifacts must never include `.env`, real raw Yandex Music exports, DuckDB files, account snapshots, recommendation CSVs from a real account, or audio.

## Release Checklist

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

The `Release` workflow runs sample-data validation, builds public docs, packages tracked source via `git archive`, and creates a GitHub release from the tag notes.

## GitHub Pages

The `GitHub Pages` workflow builds a static product site from README/docs plus sample metadata report artifacts. It intentionally clears `YANDEX_MUSIC_TOKEN` so public pages are reproducible and do not depend on a private account.
