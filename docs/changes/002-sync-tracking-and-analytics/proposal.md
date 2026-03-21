# Proposal: Sync Tracking and Analytics

## Intent

After the initial listings export (001), etsync can download shop data to local TOML files. However, there is no way to track how listings change over time, quickly navigate exported data, or analyze shop performance. This change adds three complementary features: richer index metadata for navigation, git-based sync tracking for change history, and DuckDB-powered analytics for shop performance insights.

Together these features turn etsync from a one-shot export tool into a persistent shop monitoring and analysis platform.

## Scope

### In scope

- **JSON index navigation** — Enhanced `index.json` file with richer per-listing metadata (listing URL, creation date, price, currency, tags, taxonomy, state) enabling quick browsing and filtering without opening individual TOML files
- **Git-based sync tracking** — Initialize the data directory as a git repository, auto-commit after each `pull` operation with timestamped messages, provide CLI commands to view diffs between syncs and detect listing changes over time
- **Analytics with DuckDB** — New `etsync/analytics/` module that pulls shop stats and listing stats from the Etsy API, stores them in a DuckDB database in the data directory, and exposes CLI commands for querying performance data (views, favorites, revenue)

### Out of scope

- Push/write operations (updating listings based on analytics)
- Real-time monitoring or webhook integration
- Dashboard UI or web interface
- Third-party analytics platforms integration
- Multi-shop analytics aggregation (single shop per DuckDB instance)

## Approach

1. **Index navigation** — After each `pull listings`, generate `index.json` alongside the existing `index.toml`. The JSON format enables programmatic consumption and richer nested structures (tags arrays, image URLs). A new `etsync list` command provides terminal-based browsing with filters.

2. **Git tracking** — A new `etsync/data_repo.py` module wraps `gitpython` to manage a git repo in the data directory. On first sync, it runs `git init`. After each successful pull, it stages all changes and commits with a message like `sync: 2026-03-21T14:30:00 — 47 listings`. A `etsync diff` command shows what changed between any two syncs.

3. **Analytics** — A new `etsync/analytics/` subpackage uses the Etsy API's stats endpoints to pull shop-level and listing-level performance data. Data is stored in a DuckDB database (`{data_dir}/analytics.duckdb`). CLI commands allow pulling fresh stats and running queries against historical data.

## Future

These will become separate OpenSpec changes:

- **Automated reports** — Scheduled analytics summaries emailed or sent to Slack
- **Alerts** — Threshold-based notifications (e.g., listing views drop below N)
- **Multi-shop dashboards** — Aggregate analytics across multiple shops
- **Export to CSV/Parquet** — Bulk data export from DuckDB for external tools
- **Sync conflict resolution** — Handle cases where local edits conflict with remote changes
