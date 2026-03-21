# Design: Sync Tracking and Analytics

## Technical Approach

This change adds three new capabilities to etsync. The index navigation enriches the existing listings pull pipeline. Git tracking wraps the data directory in version control. Analytics introduces a new data domain with its own API endpoints and DuckDB storage.

```
etsync/
  cli.py             # extended: new commands (list, diff, analytics group)
  data_repo.py       # NEW: git repo management for data directory
  listings/
    pull.py          # modified: generate index.json after pull
    index.py         # NEW: index.json generation and querying
  analytics/
    __init__.py      # package marker, registers CLI subcommands
    pull.py          # fetch stats from Etsy API, store in DuckDB
    db.py            # DuckDB schema, connection, insert/query helpers
    query.py         # CLI query interface for analytics data
```

## Architecture Decisions

### JSON index alongside TOML index

**Rationale**: The existing `index.toml` provides a flat summary (listing_id, title, state, updated). A parallel `index.json` adds richer nested metadata — tags arrays, image URLs, price objects — that TOML handles awkwardly. JSON also enables programmatic consumption by external tools (jq, scripts, dashboards). The TOML index is kept for human readability; the JSON index is the machine-friendly superset.

**Index JSON structure**:

```json
{
  "shop_id": 12345678,
  "synced_at": "2026-03-21T14:30:00Z",
  "listing_count": 47,
  "listings": [
    {
      "listing_id": 1234567890,
      "title": "Handmade Ceramic Mug",
      "url": "https://www.etsy.com/listing/1234567890",
      "state": "active",
      "creation_tsz": "2025-06-15T10:00:00Z",
      "last_modified_tsz": "2026-03-20T08:15:00Z",
      "price": {
        "amount": 2499,
        "divisor": 100,
        "currency_code": "EUR"
      },
      "quantity": 10,
      "tags": ["ceramic", "mug", "handmade", "gift"],
      "taxonomy_path": ["Home & Living", "Kitchen & Dining", "Drinkware", "Mugs"],
      "views": 342,
      "num_favorers": 28,
      "featured_rank": -1,
      "original_creation_tsz": "2025-06-15T10:00:00Z",
      "shop_section_id": 987654,
      "processing_min": 1,
      "processing_max": 3
    }
  ]
}
```

Fields are sourced directly from the `getListingsByShop` response (Etsy API v3). The `url` field is constructed as `https://www.etsy.com/listing/{listing_id}`. Price uses Etsy's `Money` type (amount in smallest currency unit, divisor, currency code).

### Git-based sync tracking via gitpython

**Rationale**: Git provides a robust, well-understood mechanism for tracking file changes over time. By initializing the data directory as a git repo, every sync becomes a commit, and standard git tooling (log, diff, show) can inspect the full history. `gitpython` is a mature library that avoids shelling out to git.

**Module: `etsync/data_repo.py`**

Responsibilities:
- `init_repo(data_dir)` — Run `git init` if `.git/` does not exist. Create a `.gitignore` with `analytics.duckdb` (binary, not suitable for git diffing). Return a `git.Repo` instance.
- `commit_sync(repo, message)` — Stage all changes (`git add -A`), commit with the provided message. No-op if working tree is clean.
- `get_sync_log(repo, n)` — Return the last N commits as a list of `(hash, date, message)` tuples.
- `get_diff(repo, ref_a, ref_b)` — Return the diff between two commits as a string.

**Commit message format**: `sync: {ISO timestamp} — {N} listings`

**CLI integration**:
- After each successful `etsync pull listings`, the pull command calls `init_repo()` then `commit_sync()`.
- `etsync diff` — Show diff between the two most recent syncs (or between specified commits via `--from` / `--to` flags).
- `etsync log` — Show sync history (delegates to `get_sync_log`).

**Data directory `.gitignore**:
```
analytics.duckdb
analytics.duckdb.wal
```

### DuckDB for analytics storage

**Rationale**: DuckDB is an embedded analytical database — zero configuration, single-file storage, excellent for time-series aggregation. It handles the analytical queries (trends, ranking, aggregation) that would be clumsy with flat TOML files. Unlike SQLite, DuckDB is columnar and optimized for OLAP workloads like "show me revenue by month" or "top 10 listings by views".

**Database location**: `{data_dir}/analytics.duckdb`

**Schema**:

```sql
CREATE TABLE shop_stats (
    pulled_at       TIMESTAMP NOT NULL,
    shop_id         BIGINT NOT NULL,
    num_favorers    INTEGER,
    listing_active_count INTEGER,
    digital_listing_count INTEGER,
    currency_code   VARCHAR(3),
    login_name      VARCHAR,
    PRIMARY KEY (pulled_at, shop_id)
);

CREATE TABLE listing_stats (
    pulled_at       TIMESTAMP NOT NULL,
    listing_id      BIGINT NOT NULL,
    title           VARCHAR,
    state           VARCHAR,
    views           INTEGER,
    num_favorers    INTEGER,
    price_amount    INTEGER,
    price_divisor   INTEGER,
    currency_code   VARCHAR(3),
    quantity        INTEGER,
    tags            VARCHAR[],
    taxonomy_path   VARCHAR[],
    creation_tsz    TIMESTAMP,
    last_modified_tsz TIMESTAMP,
    featured_rank   INTEGER,
    PRIMARY KEY (pulled_at, listing_id)
);

CREATE TABLE shop_receipts_summary (
    pulled_at       TIMESTAMP NOT NULL,
    shop_id         BIGINT NOT NULL,
    period_start    DATE NOT NULL,
    period_end      DATE NOT NULL,
    total_receipts  INTEGER,
    total_revenue   BIGINT,
    currency_code   VARCHAR(3),
    PRIMARY KEY (pulled_at, shop_id, period_start)
);
```

### Etsy API endpoints used

**Shop stats** — `GET /v3/application/shops/{shop_id}`
- Returns: `num_favorers`, `listing_active_count`, `digital_listing_count`, `currency_code`, `login_name`
- etsyv3 method: `EtsyAPI.get_shop(shop_id)`
- Pulled by: `etsync pull stats`

**Listing stats** — `GET /v3/application/shops/{shop_id}/listings/active`
- Returns per-listing: `views`, `num_favorers`, `price`, `quantity`, `tags`, `taxonomy_path`, `creation_tsz`, `last_modified_tsz`, `featured_rank`
- etsyv3 method: `EtsyAPI.get_shop_listing_active(shop_id, limit=100, offset=N)`
- Note: This is the same endpoint used for listings pull; analytics extracts the stats fields and inserts them into DuckDB as a time-series snapshot.
- Pulled by: `etsync pull stats`

**Shop receipts** — `GET /v3/application/shops/{shop_id}/receipts`
- Returns: receipt objects with `grandtotal`, `create_timestamp`, `was_paid`
- etsyv3 method: `EtsyAPI.get_shop_receipts(shop_id, limit=100, offset=N)`
- Aggregated into `shop_receipts_summary` by month for revenue tracking.
- Pulled by: `etsync pull stats --include-receipts` (opt-in, can be slow for large shops)

**Listing images** (for index metadata) — `GET /v3/application/listings/{listing_id}/images`
- Returns: image URLs per listing
- etsyv3 method: `EtsyAPI.get_listing_images(listing_id)`
- Note: Only called if `--include-images` flag is set on `pull listings` to avoid N+1 API calls.

### Module: `etsync/analytics/`

- `db.py` — DuckDB connection management. `get_db(data_dir)` returns a connection, creating the database and tables if they do not exist. Insert helpers for each table. Query helpers that return results as dicts.
- `pull.py` — Fetch stats from Etsy API and insert into DuckDB. `pull_shop_stats(api, shop_id, db)`, `pull_listing_stats(api, shop_id, db)`, `pull_receipts(api, shop_id, db)`.
- `query.py` — Pre-built queries exposed as CLI commands. Handles formatting output as tables.

### CLI commands

| Command | Description |
|---------|-------------|
| `etsync list` | Browse listings from index.json with optional filters (`--tag`, `--min-price`, `--sort`) |
| `etsync diff` | Show changes between two syncs (defaults to last two, or `--from`/`--to` commit refs) |
| `etsync log` | Show sync history (last N commits in the data repo) |
| `etsync pull stats` | Download shop stats + listing stats into DuckDB |
| `etsync pull stats --include-receipts` | Also pull receipt data for revenue tracking |
| `etsync analytics query` | Run a pre-built or custom SQL query against the analytics database |
| `etsync analytics top-listings` | Show top N listings by views or favorites |
| `etsync analytics revenue` | Show revenue summary by month |

## Data Flow

```
etsync pull listings
  │
  ├─ (existing flow: fetch listings, save TOML files)
  │
  ├─ listings/index.py: build index.json from fetched listings
  │    └─ json.dump(index_data, f) → write {data_dir}/listings/index.json
  │
  ├─ data_repo.py: init_repo(data_dir) — git init if needed
  └─ data_repo.py: commit_sync(repo, "sync: {timestamp} — {N} listings")

etsync pull stats
  │
  ├─ config.py: load settings
  ├─ auth check
  ├─ EtsyAPI(...)
  │
  ├─ analytics/pull.py: pull_shop_stats(api, shop_id, db)
  │    └─ GET /v3/application/shops/{shop_id}
  │    └─ INSERT INTO shop_stats
  │
  ├─ analytics/pull.py: pull_listing_stats(api, shop_id, db)
  │    └─ GET /v3/application/shops/{shop_id}/listings/active (paginated)
  │    └─ INSERT INTO listing_stats (one row per listing per pull)
  │
  ├─ (if --include-receipts)
  │    └─ analytics/pull.py: pull_receipts(api, shop_id, db)
  │         └─ GET /v3/application/shops/{shop_id}/receipts (paginated)
  │         └─ aggregate by month → INSERT INTO shop_receipts_summary
  │
  └─ data_repo.py: commit_sync(repo, "stats: {timestamp}")

etsync analytics query "SELECT ..."
  │
  └─ analytics/db.py: get_db(data_dir).execute(query) → print results
```

## File Changes

| Action | Path | Description |
|--------|------|-------------|
| Create | `etsync/data_repo.py` | Git repo init, commit, log, diff for data directory |
| Create | `etsync/listings/index.py` | Generate and query index.json |
| Create | `etsync/analytics/__init__.py` | Package marker, register CLI subcommands |
| Create | `etsync/analytics/db.py` | DuckDB schema, connection, insert/query helpers |
| Create | `etsync/analytics/pull.py` | Fetch stats from Etsy API into DuckDB |
| Create | `etsync/analytics/query.py` | Pre-built queries and custom SQL CLI |
| Modify | `etsync/cli.py` | Add `list`, `diff`, `log` commands; `analytics` group |
| Modify | `etsync/listings/pull.py` | Call index.json generation and git commit after pull |
| Modify | `pyproject.toml` | Add `gitpython`, `duckdb` dependencies |
| Create | `tests/test_data_repo.py` | Git repo management tests |
| Create | `tests/test_index.py` | Index.json generation and query tests |
| Create | `tests/test_analytics_db.py` | DuckDB schema and insert/query tests |
| Create | `tests/test_analytics_pull.py` | Stats pull tests (mocked API) |
