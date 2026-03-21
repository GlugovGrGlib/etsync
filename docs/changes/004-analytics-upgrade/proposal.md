# Proposal: Analytics Upgrade — Receipts, Transactions, Reviews & Pre-Built Queries

## Intent

The current analytics module (002) only captures listing-level snapshots from local JSON files and basic shop stats. It cannot answer the most important shop management questions: "How much revenue did I earn this month?", "Which listings actually sell?", "What do customers think of my products?" This change pulls real sales data (receipts, transactions), customer feedback (reviews), and payment details (ledger entries) from the Etsy API, and adds pre-built query commands so users get actionable insights without writing SQL.

## Scope

### In scope

- **Receipts pulling** — Fetch order/receipt data via `get_shop_receipts`, store individual receipts in DuckDB with order dates, amounts, buyer country, paid/shipped status. Aggregate into monthly revenue summaries.
- **Transactions pulling** — Fetch per-sale line items via `get_shop_receipt_transactions_by_shop`, linking each sold item back to its listing for sales-per-listing analysis.
- **Payment ledger pulling** — Fetch ledger entries via `get_shop_payment_account_ledger_entries` for actual payouts, fees, and net revenue with date ranges.
- **Reviews pulling** — Fetch shop reviews via `get_reviews_by_shop`, store ratings, review text, and associated listing IDs for sentiment and quality tracking.
- **Richer listing stats** — Align the snapshot schema with the 002 design: add tags, taxonomy_path, creation_tsz, last_modified_tsz, featured_rank to listing snapshots. Pull stats directly from the API instead of reading local JSON files.
- **Pre-built query commands** — `etsync analytics top-listings`, `etsync analytics revenue`, `etsync analytics reviews` commands with formatted output, so users don't need raw SQL for common questions.
- **Schema migration** — Upgrade the existing `listing_snapshots` and `shop_snapshots` tables to the richer schema, preserving existing data.

### Out of scope

- Dashboard UI or web interface
- Automated alerts or scheduled reports
- Multi-shop aggregation across databases
- Views/favorites/click-through rate (not available via API beyond what listings already expose)
- Expense tracking or profit margin calculation (requires non-API data)

## Approach

1. **Schema upgrade** — Migrate existing DuckDB tables to the richer schema from the 002 design. Add new tables for receipts, transactions, ledger entries, and reviews. Use DuckDB's `ALTER TABLE` where possible, recreate tables where needed.

2. **New data pullers** — Add pull functions for each new data source, following the established pattern in `analytics/pull.py`. Each puller handles pagination, inserts into DuckDB, and reports progress. Receipts and transactions are opt-in via `--include-receipts` flag. Reviews are pulled with `etsync pull reviews`.

3. **Direct API stats pulling** — Change `pull stats` to fetch listing stats directly from the Etsy API (paginated `get_listings_by_shop`) instead of reading local JSON files. This decouples analytics from the listings pull workflow and captures richer fields.

4. **Pre-built query commands** — Add subcommands under `etsync analytics` that run common queries and format the results as tables. Each command uses only the latest snapshot by default, with `--from`/`--to` date flags for historical analysis.

## Future

These will become separate OpenSpec changes:

- **Sales velocity tracking** — Compute units sold per listing per day/week/month
- **Export to CSV/Parquet** — Bulk data export from DuckDB for spreadsheets or BI tools
- **Automated reports** — Scheduled summaries emailed or sent to messaging platforms
- **Listing performance scoring** — Composite score combining views, favorites, sales, reviews
