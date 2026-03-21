# Design: Analytics Upgrade

## Technical Approach

This change enriches the analytics module with four new data sources (receipts, transactions, ledger, reviews), upgrades the listing stats schema, and adds pre-built query commands. The module structure expands but follows existing conventions.

```
etsync/
  analytics/
    __init__.py      # modified: register new CLI subcommands
    pull.py          # modified: direct API pulling, richer schema, new data sources
    query.py         # modified: add pre-built query commands
    schema.py        # NEW: schema definitions, migration logic
  cli.py             # modified: add analytics subcommand group
```

## Architecture Decisions

### Schema migration strategy

**Rationale**: The existing `listing_snapshots` table has a simpler schema than what 002 designed. Rather than dropping data, we use `ALTER TABLE ADD COLUMN` for new nullable columns. A `schema_version` metadata table tracks the current version and triggers migrations on connect.

**Migration approach**:
- `schema.py` defines `CURRENT_SCHEMA_VERSION = 2`
- On connect, read `schema_version` table (create if missing, default version 0)
- Run migrations sequentially from current to target version
- Version 0→1: original tables (already exist)
- Version 1→2: add columns to listing_snapshots, create new tables

### Direct API pulling instead of reading local JSON

**Rationale**: The current `pull stats` reads listing data from local JSON files that were saved by `pull listings`. This creates a dependency (must run `pull listings` first) and misses fields not saved to JSON. Pulling directly from the API decouples the workflows and captures richer data.

**Change**: `pull_stats()` now calls `get_listings_by_shop()` directly (paginated), extracting stats fields and inserting them into DuckDB. The local JSON dependency is removed.

### Receipts and transactions as opt-in

**Rationale**: Receipt fetching can be slow for shops with large order histories (hundreds of API pages). Transactions add another layer of API calls. Making these opt-in with `--include-receipts` avoids slowing down the default stats pull.

### Reviews as a separate pull command

**Rationale**: Reviews are a distinct data domain (feedback vs. metrics). They change infrequently and don't need to be pulled with every stats snapshot. A separate `etsync pull reviews` keeps concerns clean.

## DuckDB Schema

```sql
-- Version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER NOT NULL,
    migrated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
);

-- Listing stats (upgraded from listing_snapshots)
CREATE TABLE IF NOT EXISTS listing_snapshots (
    listing_id        BIGINT,
    title             VARCHAR,
    views             INTEGER,
    favorites         INTEGER,
    price_amount      DOUBLE,
    price_currency    VARCHAR,
    quantity          INTEGER,
    state             VARCHAR,
    snapshot_date     DATE,
    -- New in v2:
    tags              VARCHAR[],
    taxonomy_path     VARCHAR[],
    creation_tsz      TIMESTAMP,
    last_modified_tsz TIMESTAMP,
    featured_rank     INTEGER
);

-- Shop stats (upgraded from shop_snapshots)
CREATE TABLE IF NOT EXISTS shop_snapshots (
    shop_id           BIGINT,
    num_listings      INTEGER,
    snapshot_date     DATE,
    -- New in v2:
    num_favorers      INTEGER,
    digital_listing_count INTEGER,
    currency_code     VARCHAR(3),
    login_name        VARCHAR
);

-- Individual receipts (orders)
CREATE TABLE IF NOT EXISTS receipts (
    receipt_id        BIGINT NOT NULL,
    shop_id           BIGINT NOT NULL,
    buyer_email       VARCHAR,
    buyer_country     VARCHAR,
    grandtotal_amount BIGINT,
    grandtotal_currency VARCHAR(3),
    subtotal_amount   BIGINT,
    total_shipping    BIGINT,
    total_tax         BIGINT,
    status            VARCHAR,
    was_paid          BOOLEAN,
    was_shipped       BOOLEAN,
    create_timestamp  TIMESTAMP,
    update_timestamp  TIMESTAMP,
    pulled_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (receipt_id)
);

-- Monthly revenue aggregation (materialized from receipts)
CREATE TABLE IF NOT EXISTS revenue_summary (
    shop_id           BIGINT NOT NULL,
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    total_receipts    INTEGER,
    total_revenue     BIGINT,
    total_shipping    BIGINT,
    total_tax         BIGINT,
    currency_code     VARCHAR(3),
    computed_at       TIMESTAMP NOT NULL,
    PRIMARY KEY (shop_id, period_start)
);

-- Transaction line items (individual sold items)
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id    BIGINT NOT NULL,
    receipt_id        BIGINT NOT NULL,
    listing_id        BIGINT NOT NULL,
    title             VARCHAR,
    quantity          INTEGER,
    price_amount      BIGINT,
    price_currency    VARCHAR(3),
    shipping_cost     BIGINT,
    create_timestamp  TIMESTAMP,
    pulled_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (transaction_id)
);

-- Payment ledger entries
CREATE TABLE IF NOT EXISTS ledger_entries (
    entry_id          BIGINT NOT NULL,
    shop_id           BIGINT NOT NULL,
    amount            BIGINT,
    currency_code     VARCHAR(3),
    entry_type        VARCHAR,
    description       VARCHAR,
    ledger_type       VARCHAR,
    create_date       TIMESTAMP,
    pulled_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (entry_id)
);

-- Shop reviews
CREATE TABLE IF NOT EXISTS reviews (
    review_id         BIGINT NOT NULL,
    shop_id           BIGINT NOT NULL,
    listing_id        BIGINT,
    rating            INTEGER,
    review            VARCHAR,
    language          VARCHAR,
    create_timestamp  TIMESTAMP,
    update_timestamp  TIMESTAMP,
    pulled_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (review_id)
);
```

## Etsy API Endpoints Used

**Shop receipts** — `GET /v3/application/shops/{shop_id}/receipts`
- Returns: receipt objects with grandtotal, subtotal, shipping, tax, buyer info, status
- etsyv3 method: `EtsyAPI.get_shop_receipts(shop_id, limit=100, offset=N)`
- Supports filters: `was_paid`, `was_shipped`, `min_created`, `max_created`
- Pulled by: `etsync pull stats --include-receipts`

**Shop receipt transactions** — `GET /v3/application/shops/{shop_id}/transactions`
- Returns: line items with listing_id, quantity, price per transaction
- etsyv3 method: `EtsyAPI.get_shop_receipt_transactions_by_shop(shop_id, limit=100, offset=N)`
- Pulled by: `etsync pull stats --include-receipts`

**Payment ledger** — `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries`
- Returns: individual ledger entries with amount, type, description
- etsyv3 method: `EtsyAPI.get_shop_payment_account_ledger_entries(shop_id, limit=100, offset=N)`
- Supports date range: `min_created`, `max_created`
- Pulled by: `etsync pull stats --include-receipts`

**Shop reviews** — `GET /v3/application/shops/{shop_id}/reviews`
- Returns: review objects with rating, text, listing_id, timestamps
- etsyv3 method: `EtsyAPI.get_reviews_by_shop(shop_id, limit=100, offset=N)`
- Pulled by: `etsync pull reviews`

**Listings (for stats)** — `GET /v3/application/shops/{shop_id}/listings`
- Already used by `pull listings`; now also used directly by `pull stats`
- etsyv3 method: `EtsyAPI.get_listings_by_shop(shop_id, limit=100, offset=N)`

## CLI Commands

| Command | Description |
|---------|-------------|
| `etsync pull stats` | Pull shop stats + listing stats directly from API into DuckDB |
| `etsync pull stats --include-receipts` | Also pull receipts, transactions, and ledger entries |
| `etsync pull reviews` | Pull shop reviews into DuckDB |
| `etsync analytics top-listings` | Top N listings by views or favorites (`--by`, `--limit`) |
| `etsync analytics revenue` | Monthly revenue summary from receipts |
| `etsync analytics reviews` | Review summary — avg rating, distribution, recent reviews |
| `etsync analytics sales` | Sales per listing from transactions |
| `etsync query "SELECT ..."` | Existing: run arbitrary SQL (unchanged) |

## Data Flow

```
etsync pull stats
  │
  ├─ config.py: load settings (shop_id, data_dir)
  ├─ auth check
  ├─ EtsyAPI(...)
  │
  ├─ schema.py: connect_db(data_dir) → open DuckDB, run migrations
  │
  ├─ pull.py: pull_listing_stats(api, shop_id, con)
  │    └─ GET /v3/application/shops/{shop_id}/listings (paginated)
  │    └─ INSERT INTO listing_snapshots (with tags, taxonomy, etc.)
  │
  ├─ pull.py: pull_shop_stats(api, shop_id, con)
  │    └─ GET /v3/application/shops/{shop_id}
  │    └─ INSERT INTO shop_snapshots (with num_favorers, currency, etc.)
  │
  ├─ (if --include-receipts)
  │    ├─ pull.py: pull_receipts(api, shop_id, con)
  │    │    └─ GET /shops/{shop_id}/receipts (paginated)
  │    │    └─ INSERT INTO receipts
  │    │    └─ compute_revenue_summary(con) → INSERT/REPLACE INTO revenue_summary
  │    │
  │    ├─ pull.py: pull_transactions(api, shop_id, con)
  │    │    └─ GET /shops/{shop_id}/transactions (paginated)
  │    │    └─ INSERT INTO transactions
  │    │
  │    └─ pull.py: pull_ledger(api, shop_id, con)
  │         └─ GET /shops/{shop_id}/payment-account/ledger-entries (paginated)
  │         └─ INSERT INTO ledger_entries
  │
  └─ close DB

etsync pull reviews
  │
  ├─ config.py, auth, EtsyAPI(...)
  ├─ schema.py: connect_db(data_dir)
  ├─ pull.py: pull_reviews(api, shop_id, con)
  │    └─ GET /shops/{shop_id}/reviews (paginated)
  │    └─ INSERT OR REPLACE INTO reviews
  └─ close DB

etsync analytics top-listings
  │
  └─ query.py: top_listings(con, by="views", limit=10)
       └─ SELECT from listing_snapshots WHERE snapshot_date = (latest)
       └─ format_table() → print

etsync analytics revenue
  │
  └─ query.py: revenue_summary(con)
       └─ SELECT from revenue_summary ORDER BY period_start
       └─ format amounts (cents → EUR/USD with symbol)
       └─ format_table() → print

etsync analytics reviews
  │
  └─ query.py: review_summary(con)
       └─ SELECT avg(rating), count(*), rating distribution from reviews
       └─ SELECT recent reviews with listing titles
       └─ format_table() → print

etsync analytics sales
  │
  └─ query.py: sales_by_listing(con, limit=20)
       └─ SELECT listing_id, title, sum(quantity), sum(price) FROM transactions
       └─ GROUP BY listing_id JOIN listing_snapshots for title
       └─ format_table() → print
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Missing auth tokens | Print "Run `etsync login` first" and exit 1 |
| No analytics.db exists (for query commands) | Print "Run `etsync pull stats` first" and exit 1 |
| API rate limit hit during pagination | Print warning with items fetched so far, save partial data, exit 1 |
| Receipt API returns 403 (scope not granted) | Print "Add `transactions_r` scope and re-run `etsync login`" and exit 1 |
| Schema migration failure | Print migration error, do not corrupt existing data, exit 1 |
| Empty result set for query commands | Print "(no data)" with suggestion of which pull command to run |

## File Changes

| Action | Path | Description |
|--------|------|-------------|
| Create | `etsync/analytics/schema.py` | Schema definitions, versioned migrations, connect helper |
| Modify | `etsync/analytics/pull.py` | Direct API pulling, receipt/transaction/ledger/review pullers |
| Modify | `etsync/analytics/query.py` | Pre-built query commands (top-listings, revenue, reviews, sales) |
| Modify | `etsync/analytics/__init__.py` | Register new pull and analytics subcommands |
| Modify | `etsync/cli.py` | Add `analytics` group, `pull reviews` command |
| Create | `tests/test_analytics_schema.py` | Schema creation, migration, version tracking tests |
| Create | `tests/test_analytics_receipts.py` | Receipt/transaction pulling and revenue aggregation tests |
| Create | `tests/test_analytics_reviews.py` | Review pulling and summary tests |
| Modify | `tests/test_analytics.py` | Update for richer schema, direct API pulling |
