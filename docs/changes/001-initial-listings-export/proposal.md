# Proposal: Initial Listings Export

## Intent

Etsy's web UI is cumbersome for bulk shop management. We need a CLI tool (`etsync`) that can authenticate with the Etsy API and download all shop listings to local TOML files, enabling scriptable workflows, version-controlled data, and offline inspection.

This first increment stands up the full pipeline — configuration, OAuth authentication, and listings export — so the tool is usable end-to-end from day one.

## Scope

### In scope

- Project package structure (`etsync/`)
- dynaconf-based configuration with per-environment support for multi-shop reuse
- OAuth 2.0 authentication flow with token persistence and auto-refresh
- Download all active shop listings with pagination
- JSON-to-TOML conversion and per-listing file storage
- Typer CLI with concise commands: `etsync login`, `etsync pull listings`
- Test scaffold

### Out of scope

- Listing create/update/delete (push back to Etsy)
- Other data domains (orders, receipts, reviews, shipping, inventory)
- CI/CD pipeline setup

## Approach

1. **Configuration layer** — dynaconf with `settings.toml` and `.secrets.toml`. Environments allow switching between shops (`ETSYNC_ENV=shop1`). Data directory is external and configurable (defaults to `~/.etsync/data/`).

2. **Authentication** — `etsyv3.AuthHelper` handles OAuth 2.0 consent flow. Tokens persisted to `.secrets.toml` with a `refresh_save` callback for automatic renewal.

3. **Listings export** — `etsyv3.EtsyAPI` fetches active listings with transparent pagination. Each listing saved as `{listing_id}.toml` plus an `index.toml` summary.

4. **CLI** — Typer app with 2-word-max commands. Domain modules register their own subcommand groups for extensibility.

## Future

These will become separate OpenSpec changes:

- **Orders export** — download receipts/transactions to TOML
- **Listings import** — create/update listings from local TOML (round-trip editing)
- **Inventory sync** — track stock levels, bulk update
- **Shipping profiles** — export/import shipping templates
- **Reviews export** — download shop reviews for analysis
- **Diff & sync** — compare local TOML state vs live shop, show delta
- **Scheduled export** — cron-friendly mode for periodic backups
- **Multi-shop support** — manage multiple shops from one config (dynaconf environments already enable this)
