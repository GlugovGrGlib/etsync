# Spec: Pre-Built Analytics Queries

## ADDED Requirements

### `etsync analytics top-listings` MUST show top performing listings

**Scenario: Top by views (default)**
- Given listing stats exist in DuckDB
- When the user runs `etsync analytics top-listings`
- Then the top 10 listings by views from the most recent snapshot are shown
- And columns include: listing_id, title, views, favorites, price, quantity

**Scenario: Top by favorites**
- When the user runs `etsync analytics top-listings --by favorites`
- Then listings are sorted by favorites descending

**Scenario: Top by sales (requires transactions)**
- When the user runs `etsync analytics top-listings --by sales`
- And transactions data exists
- Then listings are sorted by total units sold (from transactions table)

**Scenario: Custom limit**
- When the user runs `etsync analytics top-listings --limit 5`
- Then only the top 5 listings are shown

**Scenario: Most recent snapshot used by default**
- Given stats were pulled on 2026-03-20 and 2026-03-21
- When the user runs `etsync analytics top-listings`
- Then only 2026-03-21 data is used
- And the snapshot date is shown in the output header

**Scenario: No listing stats**
- Given no listing snapshots exist
- When the user runs `etsync analytics top-listings`
- Then a message says "No listing stats found. Run `etsync pull stats` first."

### `etsync analytics revenue` MUST show monthly revenue

**Scenario: Revenue summary**
- Given `revenue_summary` has data for January and February 2026
- When the user runs `etsync analytics revenue`
- Then a table shows: month, orders, revenue, shipping, tax
- And amounts display with currency (e.g., "EUR 125.00")
- And months are sorted chronologically

**Scenario: No receipt data**
- Given `revenue_summary` is empty
- When the user runs `etsync analytics revenue`
- Then a message says "No revenue data. Run `etsync pull stats --include-receipts` first."

### `etsync analytics reviews` MUST show review insights

**Scenario: Review summary**
- Given reviews exist in DuckDB
- When the user runs `etsync analytics reviews`
- Then output shows: total reviews, average rating, rating distribution (5-star: N, 4-star: N, ...)
- And the 5 most recent reviews are listed with: rating, listing title, review text (truncated to 80 chars)

**Scenario: No reviews**
- Given no reviews exist
- When the user runs `etsync analytics reviews`
- Then a message says "No reviews found. Run `etsync pull reviews` first."

### `etsync analytics sales` MUST show sales per listing

**Scenario: Sales breakdown**
- Given transactions exist for multiple listings
- When the user runs `etsync analytics sales`
- Then a table shows: listing_id, title, units_sold, total_revenue
- And listings are sorted by units_sold descending
- And the top 20 are shown by default

**Scenario: Custom limit**
- When the user runs `etsync analytics sales --limit 50`
- Then the top 50 listings by sales are shown

**Scenario: No transaction data**
- Given no transactions exist
- When the user runs `etsync analytics sales`
- Then a message says "No sales data. Run `etsync pull stats --include-receipts` first."

### Schema migration MUST preserve existing data

**Scenario: First run after upgrade**
- Given an analytics.db with the old schema (listing_snapshots, shop_snapshots)
- When the user runs any analytics command
- Then the schema is migrated: new columns added (nullable), new tables created
- And existing snapshot data is preserved unchanged
- And schema_version is set to 2

**Scenario: Fresh install**
- Given no analytics.db exists
- When the user runs `etsync pull stats`
- Then all tables are created with the full v2 schema
- And schema_version is set to 2

**Scenario: Already migrated**
- Given analytics.db with schema_version = 2
- When the user runs any analytics command
- Then no migration runs
- And existing data is untouched
