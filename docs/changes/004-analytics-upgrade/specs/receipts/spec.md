# Spec: Receipts, Transactions & Payment Ledger

## ADDED Requirements

### Receipt pulling MUST be opt-in via `--include-receipts`

**Scenario: Pull with receipts**
- When the user runs `etsync pull stats --include-receipts`
- Then `GET /v3/application/shops/{shop_id}/receipts` is called with pagination
- And each receipt is inserted into the `receipts` table
- And a monthly `revenue_summary` is computed from the receipts

**Scenario: Pull without receipts (default)**
- When the user runs `etsync pull stats`
- Then no receipt, transaction, or ledger API calls are made

### Receipts MUST capture order-level financial data

**Scenario: Receipt data extraction**
- Given the API returns a receipt with grandtotal, subtotal, shipping, tax
- When the receipt is processed
- Then all amounts are stored in their smallest currency unit (cents)
- And buyer_country, status, was_paid, was_shipped are captured
- And create_timestamp and update_timestamp are stored

**Scenario: Duplicate receipt handling**
- Given receipt 12345 was pulled yesterday
- And the same receipt is pulled today (e.g., status changed from unpaid to paid)
- When the receipt is inserted
- Then the existing row is replaced with the updated data (INSERT OR REPLACE)

### Transactions MUST link sales to listings

**Scenario: Transaction pulling**
- When the user runs `etsync pull stats --include-receipts`
- Then `GET /v3/application/shops/{shop_id}/transactions` is called with pagination
- And each transaction row includes: transaction_id, receipt_id, listing_id, title, quantity, price_amount, price_currency

**Scenario: Sales per listing query**
- Given transactions exist for listings A (3 sales) and B (7 sales)
- When the user runs `etsync analytics sales`
- Then listing B appears first with total quantity and revenue
- And listing A appears second

### Payment ledger MUST capture fees and payouts

**Scenario: Ledger pulling**
- When the user runs `etsync pull stats --include-receipts`
- Then `GET /v3/application/shops/{shop_id}/payment-account/ledger-entries` is called
- And entries are stored with: entry_id, amount, currency_code, entry_type, description, ledger_type, create_date

**Scenario: Duplicate ledger entry handling**
- Given ledger entry 999 was already pulled
- When it appears again in a subsequent pull
- Then the existing row is replaced (INSERT OR REPLACE)

### Revenue summary MUST aggregate receipts by month

**Scenario: Monthly aggregation**
- Given paid receipts in January 2026: EUR 50.00 and EUR 75.00
- And paid receipts in February 2026: EUR 120.00
- When revenue summary is computed
- Then January row: total_receipts=2, total_revenue=12500, total_shipping and total_tax summed
- And February row: total_receipts=1, total_revenue=12000

**Scenario: Only paid receipts count toward revenue**
- Given a receipt with was_paid=false
- When revenue summary is computed
- Then that receipt is excluded from total_revenue and total_receipts

**Scenario: Revenue display formatting**
- When the user runs `etsync analytics revenue`
- Then amounts are formatted with currency symbol (e.g., "EUR 125.00" not "12500")
- And months are sorted chronologically
- And columns include: month, orders, revenue, shipping, tax

### Missing scope MUST produce a clear error

**Scenario: Receipt scope not granted**
- Given the OAuth token does not include `transactions_r` scope
- When the user runs `etsync pull stats --include-receipts`
- Then the API returns 403
- And etsync prints: "Add `transactions_r` scope and re-run `etsync login`"
- And exits with code 1

### Pagination MUST handle large order histories

**Scenario: Shop with 500+ receipts**
- Given the shop has 500 receipts
- When the user runs `etsync pull stats --include-receipts`
- Then all receipts are fetched via paginated API calls (limit=100, incrementing offset)
- And all 500 receipts are stored in DuckDB

**Scenario: Progress reporting**
- Given a large receipt pull is in progress
- Then progress is printed to stderr: "Fetched 100/500 receipts..."
