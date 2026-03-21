# Spec: Analytics with DuckDB

## ADDED Requirements

### DuckDB database MUST be created automatically

**Scenario: First stats pull**
- Given the data directory exists
- And no `analytics.duckdb` file exists
- When the user runs `etsync pull stats`
- Then `analytics.duckdb` is created at `{data_dir}/analytics.duckdb`
- And the schema tables (`shop_stats`, `listing_stats`, `shop_receipts_summary`) are created

**Scenario: Subsequent stats pull**
- Given `analytics.duckdb` already exists with the correct schema
- When the user runs `etsync pull stats`
- Then the existing database is reused
- And new rows are inserted (not replacing existing data)

### `etsync pull stats` MUST download shop and listing statistics

**Scenario: Shop stats pull**
- Given valid authentication tokens
- When the user runs `etsync pull stats`
- Then `GET /v3/application/shops/{shop_id}` is called via `EtsyAPI.get_shop(shop_id)`
- And a row is inserted into `shop_stats` with: `pulled_at`, `shop_id`, `num_favorers`, `listing_active_count`, `digital_listing_count`, `currency_code`, `login_name`

**Scenario: Listing stats pull**
- Given valid authentication tokens
- And the shop has active listings
- When the user runs `etsync pull stats`
- Then `GET /v3/application/shops/{shop_id}/listings/active` is called with pagination via `EtsyAPI.get_shop_listing_active(shop_id, limit=100, offset=N)`
- And one row per listing is inserted into `listing_stats` with: `pulled_at`, `listing_id`, `title`, `state`, `views`, `num_favorers`, `price_amount`, `price_divisor`, `currency_code`, `quantity`, `tags`, `taxonomy_path`, `creation_tsz`, `last_modified_tsz`, `featured_rank`

**Scenario: Stats are time-series snapshots**
- Given a listing with `listing_id` 123 was pulled yesterday with 100 views
- And the same listing is pulled today with 120 views
- Then both rows exist in `listing_stats` (different `pulled_at` timestamps)
- And querying can show the delta of +20 views

### Receipt pulling MUST be opt-in

**Scenario: Pull with receipts**
- When the user runs `etsync pull stats --include-receipts`
- Then `GET /v3/application/shops/{shop_id}/receipts` is called via `EtsyAPI.get_shop_receipts(shop_id, limit=100, offset=N)` with pagination
- And receipts are aggregated by calendar month
- And rows are inserted into `shop_receipts_summary` with: `pulled_at`, `shop_id`, `period_start`, `period_end`, `total_receipts`, `total_revenue`, `currency_code`

**Scenario: Pull without receipts (default)**
- When the user runs `etsync pull stats`
- Then no receipt API calls are made
- And `shop_receipts_summary` is not updated

**Scenario: Revenue aggregation**
- Given receipts in January 2026 with totals of EUR 50.00 and EUR 75.00
- When receipts are aggregated
- Then `shop_receipts_summary` contains a row with `period_start=2026-01-01`, `period_end=2026-01-31`, `total_receipts=2`, `total_revenue=12500` (in cents), `currency_code="EUR"`

### No authentication MUST be handled gracefully

**Scenario: Missing tokens**
- Given no valid tokens exist
- When the user runs `etsync pull stats`
- Then a clear error instructs the user to run `etsync login` first

### `etsync analytics query` MUST execute arbitrary SQL

**Scenario: Custom SQL query**
- Given `analytics.duckdb` exists with data
- When the user runs `etsync analytics query "SELECT listing_id, views FROM listing_stats ORDER BY views DESC LIMIT 5"`
- Then the query executes against the database
- And results are displayed in a table format

**Scenario: Invalid SQL**
- When the user runs `etsync analytics query "SELECT * FROM nonexistent_table"`
- Then the DuckDB error message is displayed clearly

**Scenario: No database**
- Given no `analytics.duckdb` exists
- When the user runs `etsync analytics query "SELECT 1"`
- Then a clear error instructs the user to run `etsync pull stats` first

### `etsync analytics top-listings` MUST show top performing listings

**Scenario: Top by views (default)**
- Given listing stats exist in DuckDB
- When the user runs `etsync analytics top-listings`
- Then the top 10 listings by views from the most recent pull are shown
- And columns include: listing_id, title, views, num_favorers, price

**Scenario: Top by favorites**
- When the user runs `etsync analytics top-listings --by favorites`
- Then listings are sorted by `num_favorers` descending

**Scenario: Custom limit**
- When the user runs `etsync analytics top-listings --limit 5`
- Then only the top 5 listings are shown

**Scenario: Multiple snapshots**
- Given stats have been pulled on multiple dates
- When the user runs `etsync analytics top-listings`
- Then only the most recent snapshot is used for ranking

### `etsync analytics revenue` MUST show monthly revenue

**Scenario: Revenue summary**
- Given `shop_receipts_summary` has data for multiple months
- When the user runs `etsync analytics revenue`
- Then a table is displayed with columns: month, total_receipts, total_revenue (formatted with currency symbol)
- And months are sorted chronologically

**Scenario: No receipt data**
- Given `shop_receipts_summary` is empty
- When the user runs `etsync analytics revenue`
- Then a message indicates no receipt data and suggests running `etsync pull stats --include-receipts`

### Analytics MUST use the latest snapshot for queries by default

**Scenario: Default snapshot selection**
- Given listing stats were pulled at 2026-03-20 and 2026-03-21
- When the user runs `etsync analytics top-listings`
- Then only the 2026-03-21 data is used
- And the pull timestamp is shown in the output header

### Stats pull MUST handle pagination

**Scenario: Large shop with many listings**
- Given the shop has 250 active listings
- When the user runs `etsync pull stats`
- Then three API pages are fetched (100 + 100 + 50)
- And all 250 listing stat rows are inserted into DuckDB

**Scenario: Large receipt history**
- Given the shop has 500+ receipts
- When the user runs `etsync pull stats --include-receipts`
- Then all receipts are fetched with pagination
- And they are correctly aggregated by month
