# Tasks: Analytics Upgrade

## 1. Schema Migration

- [ ] 1.1 Create `etsync/analytics/schema.py` — schema version table, migration runner, `connect_db()` helper
- [ ] 1.2 Implement migration v0→1: recognize existing tables as version 1
- [ ] 1.3 Implement migration v1→2: `ALTER TABLE listing_snapshots ADD COLUMN` for tags, taxonomy_path, creation_tsz, last_modified_tsz, featured_rank
- [ ] 1.4 Implement migration v1→2: `ALTER TABLE shop_snapshots ADD COLUMN` for num_favorers, digital_listing_count, currency_code, login_name
- [ ] 1.5 Implement migration v1→2: create receipts, revenue_summary, transactions, ledger_entries, reviews tables
- [ ] 1.6 Create `tests/test_analytics_schema.py` — test fresh creation, migration from v1, idempotency
- [ ] 1.7 Run `ruff check`, `ruff format --check`, `ty check`

## 2. Direct API Stats Pulling

- [ ] 2.1 Refactor `pull_stats()` to fetch listings directly from API via `get_listings_by_shop()` (paginated) instead of reading local JSON files
- [ ] 2.2 Extract richer fields: tags, taxonomy_path, creation_tsz, last_modified_tsz, featured_rank
- [ ] 2.3 Pull richer shop stats: num_favorers, digital_listing_count, currency_code, login_name
- [ ] 2.4 Use `connect_db()` from schema.py instead of manual connection + `_ensure_tables()`
- [ ] 2.5 Update `tests/test_analytics.py` for new schema and direct API pulling
- [ ] 2.6 Run `ruff check`, `ruff format --check`, `ty check`

## 3. Receipt & Transaction Pulling

- [ ] 3.1 Implement `pull_receipts(api, shop_id, con)` — paginated fetch, INSERT OR REPLACE into receipts table
- [ ] 3.2 Implement `compute_revenue_summary(con, shop_id)` — aggregate paid receipts by month into revenue_summary
- [ ] 3.3 Implement `pull_transactions(api, shop_id, con)` — paginated fetch, INSERT OR REPLACE into transactions table
- [ ] 3.4 Implement `pull_ledger(api, shop_id, con)` — paginated fetch, INSERT OR REPLACE into ledger_entries
- [ ] 3.5 Add `--include-receipts` flag to `pull_stats()` — calls receipt, transaction, and ledger pullers
- [ ] 3.6 Handle 403 scope error with clear message about `transactions_r` scope
- [ ] 3.7 Add progress reporting for large pulls (stderr)
- [ ] 3.8 Create `tests/test_analytics_receipts.py` — test receipt insertion, revenue aggregation, duplicate handling, pagination
- [ ] 3.9 Run `ruff check`, `ruff format --check`, `ty check`

## 4. Review Pulling

- [ ] 4.1 Implement `pull_reviews(api, shop_id, con)` — paginated fetch, INSERT OR REPLACE into reviews
- [ ] 4.2 Add `etsync pull reviews` command to CLI
- [ ] 4.3 Create `tests/test_analytics_reviews.py` — test review insertion, duplicate handling
- [ ] 4.4 Run `ruff check`, `ruff format --check`, `ty check`

## 5. Pre-Built Query Commands

- [ ] 5.1 Add `analytics` Typer group to cli.py
- [ ] 5.2 Implement `top_listings(con, by, limit)` query function — latest snapshot, sortable by views/favorites/sales
- [ ] 5.3 Add `etsync analytics top-listings` command with `--by` and `--limit` flags
- [ ] 5.4 Implement `revenue_summary(con)` query function — monthly aggregation with currency formatting
- [ ] 5.5 Add `etsync analytics revenue` command
- [ ] 5.6 Implement `review_summary(con)` query function — avg rating, distribution, recent reviews
- [ ] 5.7 Add `etsync analytics reviews` command
- [ ] 5.8 Implement `sales_by_listing(con, limit)` query function — units sold per listing from transactions
- [ ] 5.9 Add `etsync analytics sales` command with `--limit` flag
- [ ] 5.10 Update `etsync/analytics/__init__.py` to register all new commands
- [ ] 5.11 Run `ruff check`, `ruff format --check`, `ty check`

## 6. Finalize

- [ ] 6.1 Run full CI: `ruff check`, `ruff format --check`, `ty check`
- [ ] 6.2 Run `pytest` — all tests pass
- [ ] 6.3 Manual smoke test: `etsync pull stats` (verify richer schema, direct API pull)
- [ ] 6.4 Manual smoke test: `etsync pull stats --include-receipts` (verify receipts, transactions, ledger)
- [ ] 6.5 Manual smoke test: `etsync pull reviews`
- [ ] 6.6 Manual smoke test: `etsync analytics top-listings`, `revenue`, `reviews`, `sales`
