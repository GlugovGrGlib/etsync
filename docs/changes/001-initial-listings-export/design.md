# Design: Initial Listings Export

## Technical Approach

The tool is a Python CLI application built with Typer. It wraps the `etsyv3` library for Etsy API access, uses `dynaconf` for configuration, `tomllib` (stdlib) for TOML reading, and `tomli-w` for TOML writing.

```
etsync/
  __init__.py        # package marker
  __main__.py        # entry: calls cli.app()
  cli.py             # root Typer app, registers subcommands
  config.py          # dynaconf settings singleton
  auth.py            # OAuth 2.0 login + token persistence
  listings/
    __init__.py
    pull.py          # fetch listings from API, save as TOML
```

## Architecture Decisions

### Config via dynaconf with environments

**Rationale**: dynaconf natively supports TOML settings files, environment-based overrides (`ETSYNC_ENV`), and validators. This lets one installation serve multiple shops without code changes.

Settings files live in the project root (gitignored `.secrets.toml`):
- `settings.toml` — `shop_id`, `api_base_url` (default: `https://api.etsy.com`), `data_dir` (default: `~/.etsync/data/`)
- `.secrets.toml` — `api_keystring`, `access_token`, `refresh_token`, `expires_at`

### External data directory

**Rationale**: Synced data must not live in the git repo to keep the tool reusable across shops. `data_dir` is configurable per environment, defaulting to `~/.etsync/data/`. Each domain gets a subdirectory (e.g., `{data_dir}/listings/`).

### Typer for CLI

**Rationale**: Typer provides type-hint-driven argument parsing, auto-generated help, and composable command groups with minimal boilerplate. Commands stay at 2-word depth.

CLI structure:
- `etsync login` — top-level command in `cli.py`, delegates to `auth.py`
- `etsync pull listings` — `pull` is a Typer group, `listings` is a command registered by the listings module

### etsyv3 for API access

**Rationale**: Already handles OAuth 2.0 flow, token refresh, and wraps 60+ Etsy endpoints. `refresh_save` callback persists new tokens to `.secrets.toml` automatically.

### One file per listing + index

**Rationale**: Per-listing files make diffing, grepping, and selective processing easy. `index.toml` provides a quick overview without parsing every file.

## Data Flow

```
etsync pull listings
  │
  ├─ config.py: load settings (shop_id, data_dir, tokens)
  ├─ auth check: verify tokens exist, fail early if not
  ├─ EtsyAPI(keystring, token, refresh_token, expiry, refresh_save=...)
  │
  ├─ Loop: get_shop_listing_active(shop_id, limit=100, offset=N)
  │    └─ yields listing dicts (JSON)
  │
  ├─ For each listing:
  │    └─ tomli_w.dump(listing, f) → write {data_dir}/listings/{listing_id}.toml
  │
  └─ Write index.toml (listing_id, title, state, updated timestamp per entry)
```

## File Changes

| Action | Path | Description |
|--------|------|-------------|
| Create | `etsync/__init__.py` | Package marker |
| Create | `etsync/__main__.py` | `from .cli import app; app()` |
| Create | `etsync/cli.py` | Root Typer app, `login` command, `pull` group |
| Create | `etsync/config.py` | dynaconf settings with validators |
| Create | `etsync/auth.py` | OAuth flow, token save/load |
| Create | `etsync/listings/__init__.py` | Package marker |
| Create | `etsync/listings/pull.py` | Fetch + paginate + save listings as TOML |
| Create | `settings.toml` | Default config template |
| Create | `tests/__init__.py` | Test package |
| Create | `tests/test_config.py` | Config loading tests |
| Create | `tests/test_listings.py` | Listings export tests (mocked API) |
| Modify | `pyproject.toml` | Name, scripts, typer dep |
| Modify | `.gitignore` | Add `data/`, `.secrets.toml` |
| Modify | `CLAUDE.md` | Updated package name and commands |
