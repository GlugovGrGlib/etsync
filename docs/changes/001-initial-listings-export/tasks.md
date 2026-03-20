# Tasks: Initial Listings Export

## 1. Project Setup

- [ ] 1.1 Rename package directory to `etsync/`
- [ ] 1.2 Update `pyproject.toml` (name, scripts entry, typer dep)
- [ ] 1.3 Add `data/` and `.secrets.toml` to `.gitignore`
- [ ] 1.4 Create `etsync/__init__.py`
- [ ] 1.5 Create `etsync/__main__.py`
- [ ] 1.6 Run `uv sync` to install deps

## 2. Configuration

- [ ] 2.1 Create `etsync/config.py` with dynaconf settings, validators, environment support
- [ ] 2.2 Create `settings.toml` template with defaults (`api_base_url`, `data_dir`)
- [ ] 2.3 Create `tests/test_config.py` — validate loading, defaults, missing-key errors

## 3. CLI Skeleton

- [ ] 3.1 Create `etsync/cli.py` — root Typer app, `login` command, `pull` group
- [ ] 3.2 Verify `etsync --help` and `etsync pull --help` work

## 4. Authentication

- [ ] 4.1 Create `etsync/auth.py` — OAuth flow using `etsyv3.AuthHelper`
- [ ] 4.2 Implement token persistence to `.secrets.toml`
- [ ] 4.3 Implement `refresh_save` callback for auto token renewal
- [ ] 4.4 Wire `login` command in CLI to auth flow

## 5. Listings Export

- [ ] 5.1 Create `etsync/listings/__init__.py`
- [ ] 5.2 Create `etsync/listings/pull.py` — fetch all active listings with pagination
- [ ] 5.3 Implement JSON-to-TOML conversion and per-listing file write
- [ ] 5.4 Implement `index.toml` generation
- [ ] 5.5 Register `listings` command under `pull` group in CLI
- [ ] 5.6 Create `tests/test_listings.py` — mock API, verify TOML output

## 6. Finalize

- [ ] 6.1 Update `CLAUDE.md` with new package name and CLI commands
- [ ] 6.2 Run full CI checks: `ruff check`, `ruff format --check`, `ty check`
- [ ] 6.3 Run `pytest` — all tests pass
- [ ] 6.4 Manual smoke test: `etsync login` + `etsync pull listings`
