# CLAUDE.md

## Project Overview

**etsync** — CLI tool for scriptable Etsy shop management. Export/import shop data via the Etsy REST API. Data stored locally as TOML (API returns JSON, we convert). Reusable across shops — synced data lives outside the git repo in a configurable directory.

## Tech Stack & Tooling

- **Package**: `etsync/` (Python 3.12+)
- **CLI**: `typer` — command name is `etsync`
- **Config**: `dynaconf` with per-environment support for multi-shop use
- **API**: `etsyv3` (Etsy Open API v3, OAuth 2.0)
- **Serialization**: `tomllib` (stdlib, read) + `tomli-w` (write) + `json` (stdlib)

### Commands

```bash
uv sync                      # install dependencies
etsync --help                # CLI help
etsync login                 # OAuth 2.0 authentication
etsync pull listings         # download all listings to TOML
uv run pytest                # run all tests
uv run pytest tests/test_foo.py::test_bar  # run single test
uv run ruff check .          # lint
uv run ruff format .         # format
uv run ty check              # type check
```

## Quality Requirements

- Every major change must include tests and pass all CI checks: `ruff check`, `ruff format --check`, and `ty check`.
- Don't silence types/lint errors ever.

## Architecture Principles

- **Separate modules per function domain** — each concern (listings, orders, inventory) is its own subpackage under `etsync/`. Domain modules register their own CLI subcommands.
- **TOML as local data format** — all exported shop data is saved as TOML. JSON from the API is converted on ingest.
- **Data directory** — synced data lives in `pwd/.etsync/{env_name}/` (e.g., `.etsync/glugowskimetalartist/`). JSON from API goes to `listings/*.json`, analytics to `analytics.db`. The `~/.etsync/data/` path is NOT the active data dir — config defaults to project-root `.etsync/`.
- **dynaconf for config** — `settings.toml` (shop_id, data_dir) + `.secrets.toml` (api_keystring, tokens). Use `ETSYNC_ENV` to switch shops. Never commit secrets.
- **OpenSpec for planning** — design docs live in `docs/changes/` following the OpenSpec artifact format (proposal, specs, design, tasks).

## Implementation guidance

- Always create tests that make sense in the context, in case there's an ambiguity ask human. Don't use mocks in case it's not neccessary.
