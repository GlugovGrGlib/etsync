# Tasks: Sync Tracking and Analytics

## 1. Dependencies and Setup

- [ ] 1.1 Add `gitpython` to `pyproject.toml` dependencies
- [ ] 1.2 Add `duckdb` to `pyproject.toml` dependencies
- [ ] 1.3 Run `uv sync` to install new deps

## 2. JSON Index Navigation

- [ ] 2.1 Create `etsync/listings/index.py` — `build_index(listings, shop_id)` returns the index dict
- [ ] 2.2 Implement `write_index_json(index_data, data_dir)` — writes `{data_dir}/listings/index.json`
- [ ] 2.3 Implement `load_index(data_dir)` — reads and returns the index from JSON
- [ ] 2.4 Implement `filter_listings(index, tag=None, min_price=None, max_price=None, sort_by=None)` — filter/sort helpers
- [ ] 2.5 Modify `etsync/listings/pull.py` — call `build_index` and `write_index_json` after saving TOML files
- [ ] 2.6 Add `etsync list` command to `cli.py` — display listings from index.json with `--tag`, `--min-price`, `--sort` flags
- [ ] 2.7 Create `tests/test_index.py` — test index generation, JSON structure, filtering, sorting
- [ ] 2.8 Run `ruff check`, `ruff format --check`, `ty check`

## 3. Git-Based Sync Tracking

- [ ] 3.1 Create `etsync/data_repo.py` — `init_repo(data_dir)` function, creates `.gitignore` for DuckDB files
- [ ] 3.2 Implement `commit_sync(repo, message)` — stage all, commit; no-op if clean
- [ ] 3.3 Implement `get_sync_log(repo, n)` — return last N commits as tuples
- [ ] 3.4 Implement `get_diff(repo, ref_a, ref_b)` — return diff string between two commits
- [ ] 3.5 Modify `etsync/listings/pull.py` — call `init_repo` and `commit_sync` after successful pull
- [ ] 3.6 Add `etsync diff` command to `cli.py` — show diff between syncs (`--from`, `--to` flags)
- [ ] 3.7 Add `etsync log` command to `cli.py` — show sync history
- [ ] 3.8 Create `tests/test_data_repo.py` — test init, commit, log, diff with a temp directory
- [ ] 3.9 Run `ruff check`, `ruff format --check`, `ty check`

## 4. Analytics — DuckDB Storage

- [ ] 4.1 Create `etsync/analytics/__init__.py` — package marker
- [ ] 4.2 Create `etsync/analytics/db.py` — `get_db(data_dir)` returns DuckDB connection, auto-creates schema
- [ ] 4.3 Implement `insert_shop_stats(db, stats_row)` helper
- [ ] 4.4 Implement `insert_listing_stats(db, rows)` helper (batch insert)
- [ ] 4.5 Implement `insert_receipts_summary(db, rows)` helper
- [ ] 4.6 Create `tests/test_analytics_db.py` — test schema creation, inserts, queries with in-memory DuckDB

## 5. Analytics — Etsy API Pull

- [ ] 5.1 Create `etsync/analytics/pull.py` — `pull_shop_stats(api, shop_id, db)` using `GET /v3/application/shops/{shop_id}`
- [ ] 5.2 Implement `pull_listing_stats(api, shop_id, db)` — paginated fetch from `GET /v3/application/shops/{shop_id}/listings/active`, insert stats rows
- [ ] 5.3 Implement `pull_receipts(api, shop_id, db)` — paginated fetch from `GET /v3/application/shops/{shop_id}/receipts`, aggregate by month
- [ ] 5.4 Add `etsync pull stats` command to CLI — calls shop stats + listing stats pull
- [ ] 5.5 Add `--include-receipts` flag to `etsync pull stats`
- [ ] 5.6 Wire git commit after stats pull (reuse `data_repo.commit_sync`)
- [ ] 5.7 Create `tests/test_analytics_pull.py` — mock API responses, verify DuckDB inserts

## 6. Analytics — Query Interface

- [ ] 6.1 Create `etsync/analytics/query.py` — pre-built query functions (`top_listings`, `revenue_by_month`, `stats_over_time`)
- [ ] 6.2 Add `etsync analytics` group to CLI
- [ ] 6.3 Add `etsync analytics query` command — run arbitrary SQL against analytics.duckdb
- [ ] 6.4 Add `etsync analytics top-listings` command — `--by views|favorites`, `--limit N`
- [ ] 6.5 Add `etsync analytics revenue` command — monthly revenue summary table
- [ ] 6.6 Create `tests/test_analytics_query.py` — test pre-built queries with seeded DuckDB data

## 7. Finalize

- [ ] 7.1 Update `CLAUDE.md` with new CLI commands and module descriptions
- [ ] 7.2 Run full CI checks: `ruff check`, `ruff format --check`, `ty check`
- [ ] 7.3 Run `pytest` — all tests pass
- [ ] 7.4 Manual smoke test: `etsync pull listings` (verify index.json + git commit)
- [ ] 7.5 Manual smoke test: `etsync pull stats` (verify DuckDB populated)
- [ ] 7.6 Manual smoke test: `etsync analytics top-listings`
- [ ] 7.7 Manual smoke test: `etsync diff` and `etsync log`
