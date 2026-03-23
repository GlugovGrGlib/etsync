"""Fetch shop stats, receipts, transactions, ledger entries, and reviews into DuckDB."""

import sys
from datetime import date, datetime, timezone

import duckdb
import typer

from etsync.analytics.schema import connect_db
from etsync.config import get_data_dir, settings

LIMIT = 100


def _get_api():  # noqa: ANN202
    from etsync.listings.pull import _get_api

    return _get_api()


def _ts_to_datetime(ts: int | None) -> datetime | None:
    if ts is None or ts == 0:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def pull_listing_stats(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> int:  # noqa: ANN001
    """Fetch listings directly from API and insert snapshot rows."""
    today = date.today()
    offset = 0
    count = 0
    while True:
        resp = api.get_listings_by_shop(shop_id, limit=LIMIT, offset=offset)
        results = resp.get("results", [])
        total = resp.get("count", 0)
        for listing in results:
            listing_id = listing.get("listing_id", 0)
            title = listing.get("title", "")
            views = listing.get("views", 0)
            favorites = listing.get("num_favorers", 0)

            price_obj = listing.get("price", {})
            if isinstance(price_obj, dict):
                price_amount = price_obj.get("amount", 0)
                price_currency = price_obj.get("currency_code", "")
            else:
                price_amount = float(price_obj) if price_obj else 0.0
                price_currency = listing.get("currency_code", "")

            # Etsy returns price as integer cents
            if isinstance(price_amount, int):
                price_amount = price_amount / 100.0

            quantity = listing.get("quantity", 0)
            state = listing.get("state", "")
            tags = listing.get("tags", [])
            taxonomy_path = listing.get("taxonomy_path", [])
            creation_tsz = _ts_to_datetime(listing.get("creation_timestamp"))
            last_modified_tsz = _ts_to_datetime(listing.get("last_modified_timestamp"))
            featured_rank = listing.get("featured_rank")

            con.execute(
                """
                INSERT INTO listing_snapshots
                    (listing_id, title, views, favorites, price_amount, price_currency,
                     quantity, state, snapshot_date, tags, taxonomy_path,
                     creation_tsz, last_modified_tsz, featured_rank)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    listing_id,
                    title,
                    views,
                    favorites,
                    price_amount,
                    price_currency,
                    quantity,
                    state,
                    today,
                    tags,
                    taxonomy_path,
                    creation_tsz,
                    last_modified_tsz,
                    featured_rank,
                ],
            )
            count += 1

        if offset + LIMIT >= total:
            break
        offset += LIMIT
        print(f"Fetched {count}/{total} listings...", file=sys.stderr)

    return count


def pull_shop_stats(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> None:  # noqa: ANN001
    """Fetch shop info from API and insert a shop snapshot row."""
    today = date.today()
    shop_info = api.get_shop(shop_id=shop_id)

    num_listings = shop_info.get("listing_active_count", 0)
    num_favorers = shop_info.get("num_favorers", 0)
    digital_listing_count = shop_info.get("digital_listing_count", 0)
    currency_code = shop_info.get("currency_code", "")
    login_name = shop_info.get("login_name", "")

    con.execute(
        """
        INSERT INTO shop_snapshots
            (shop_id, num_listings, snapshot_date, num_favorers,
             digital_listing_count, currency_code, login_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [shop_id, num_listings, today, num_favorers, digital_listing_count, currency_code, login_name],
    )


def pull_receipts(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> int:  # noqa: ANN001
    """Fetch all receipts from API, INSERT OR REPLACE into receipts table."""
    now = datetime.now(tz=timezone.utc)
    offset = 0
    count = 0
    while True:
        try:
            resp = api.get_shop_receipts(shop_id, limit=LIMIT, offset=offset)
        except Exception as exc:
            if "Forbidden" in type(exc).__name__ or "scope" in str(exc).lower():
                typer.echo(
                    "Add `transactions_r` scope and re-run `etsync login`.",
                    err=True,
                )
                raise typer.Exit(code=1)
            raise
        results = resp.get("results", [])
        total = resp.get("count", 0)
        for receipt in results:
            grandtotal = receipt.get("grandtotal", {})
            subtotal = receipt.get("subtotal", {})
            total_shipping = receipt.get("total_shipping_cost", {})
            total_tax = receipt.get("total_tax_cost", {})

            con.execute(
                """
                INSERT OR REPLACE INTO receipts
                    (receipt_id, shop_id, buyer_email, buyer_country,
                     grandtotal_amount, grandtotal_currency, subtotal_amount,
                     total_shipping, total_tax, status, was_paid, was_shipped,
                     create_timestamp, update_timestamp, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    receipt.get("receipt_id"),
                    shop_id,
                    receipt.get("buyer_email", ""),
                    receipt.get("formatted_address", {}).get("country_iso", "")
                    if isinstance(receipt.get("formatted_address"), dict)
                    else "",
                    grandtotal.get("amount") if isinstance(grandtotal, dict) else grandtotal,
                    grandtotal.get("currency_code", "") if isinstance(grandtotal, dict) else "",
                    subtotal.get("amount") if isinstance(subtotal, dict) else subtotal,
                    total_shipping.get("amount") if isinstance(total_shipping, dict) else total_shipping,
                    total_tax.get("amount") if isinstance(total_tax, dict) else total_tax,
                    receipt.get("status", ""),
                    receipt.get("was_paid", False),
                    receipt.get("was_shipped", False),
                    _ts_to_datetime(receipt.get("create_timestamp")),
                    _ts_to_datetime(receipt.get("update_timestamp")),
                    now,
                ],
            )
            count += 1

        if offset + LIMIT >= total:
            break
        offset += LIMIT
        print(f"Fetched {count}/{total} receipts...", file=sys.stderr)

    return count


def compute_revenue_summary(con: duckdb.DuckDBPyConnection, shop_id: int) -> None:
    """Aggregate paid receipts by month into revenue_summary."""
    con.execute("DELETE FROM revenue_summary WHERE shop_id = ?", [shop_id])
    con.execute(
        """
        INSERT INTO revenue_summary
            (shop_id, period_start, period_end, total_receipts,
             total_revenue, total_shipping, total_tax, currency_code, computed_at)
        SELECT
            ?,
            DATE_TRUNC('month', create_timestamp)::DATE AS period_start,
            LAST_DAY(create_timestamp) AS period_end,
            COUNT(*) AS total_receipts,
            SUM(grandtotal_amount) AS total_revenue,
            SUM(total_shipping) AS total_shipping,
            SUM(total_tax) AS total_tax,
            grandtotal_currency AS currency_code,
            current_timestamp AS computed_at
        FROM receipts
        WHERE was_paid = true AND shop_id = ?
        GROUP BY DATE_TRUNC('month', create_timestamp), LAST_DAY(create_timestamp), grandtotal_currency
        ORDER BY period_start
        """,
        [shop_id, shop_id],
    )


def pull_transactions(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> int:  # noqa: ANN001
    """Fetch all transactions from API, INSERT OR REPLACE into transactions table."""
    now = datetime.now(tz=timezone.utc)
    offset = 0
    count = 0
    while True:
        resp = api.get_shop_receipt_transactions_by_shop(shop_id, limit=LIMIT, offset=offset)
        results = resp.get("results", [])
        total = resp.get("count", 0)
        for txn in results:
            price = txn.get("price", {})
            shipping = txn.get("shipping_cost", {})
            con.execute(
                """
                INSERT OR REPLACE INTO transactions
                    (transaction_id, receipt_id, listing_id, title, quantity,
                     price_amount, price_currency, shipping_cost, create_timestamp, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    txn.get("transaction_id"),
                    txn.get("receipt_id"),
                    txn.get("listing_id"),
                    txn.get("title", ""),
                    txn.get("quantity", 0),
                    price.get("amount") if isinstance(price, dict) else price,
                    price.get("currency_code", "") if isinstance(price, dict) else "",
                    shipping.get("amount") if isinstance(shipping, dict) else shipping,
                    _ts_to_datetime(txn.get("create_timestamp")),
                    now,
                ],
            )
            count += 1

        if offset + LIMIT >= total:
            break
        offset += LIMIT
        print(f"Fetched {count}/{total} transactions...", file=sys.stderr)

    return count


LEDGER_WINDOW = 30 * 24 * 3600  # 30 days in seconds (API max is 31 days)


def pull_ledger(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> int:  # noqa: ANN001
    """Fetch all ledger entries from API, INSERT OR REPLACE into ledger_entries table."""
    now = datetime.now(tz=timezone.utc)
    count = 0
    # Walk backwards in 30-day windows for the last 2 years
    end_ts = int(now.timestamp())
    earliest = end_ts - (2 * 365 * 24 * 3600)

    while end_ts > earliest:
        start_ts = max(end_ts - LEDGER_WINDOW, earliest)
        count += _pull_ledger_window(api, shop_id, con, start_ts, end_ts)
        end_ts = start_ts

    return count


def _pull_ledger_window(api, shop_id: int, con: duckdb.DuckDBPyConnection, min_created: int, max_created: int) -> int:  # noqa: ANN001
    """Fetch ledger entries for a single time window."""
    now = datetime.now(tz=timezone.utc)
    offset = 0
    count = 0
    while True:
        resp = api.get_shop_payment_account_ledger_entries(
            shop_id, min_created=min_created, max_created=max_created, limit=LIMIT, offset=offset
        )
        results = resp.get("results", [])
        total = resp.get("count", 0)
        for entry in results:
            con.execute(
                """
                INSERT OR REPLACE INTO ledger_entries
                    (entry_id, shop_id, amount, currency_code, entry_type,
                     description, ledger_type, create_date, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    entry.get("entry_id"),
                    shop_id,
                    entry.get("amount", {}).get("amount")
                    if isinstance(entry.get("amount"), dict)
                    else entry.get("amount"),
                    entry.get("amount", {}).get("currency_code", "")
                    if isinstance(entry.get("amount"), dict)
                    else entry.get("currency_code", ""),
                    entry.get("entry_type", ""),
                    entry.get("description", ""),
                    entry.get("ledger_type", ""),
                    _ts_to_datetime(entry.get("create_date")),
                    now,
                ],
            )
            count += 1

        if offset + LIMIT >= total:
            break
        offset += LIMIT
        print(f"Fetched {count}/{total} ledger entries...", file=sys.stderr)

    return count


def pull_reviews(api, shop_id: int, con: duckdb.DuckDBPyConnection) -> int:  # noqa: ANN001
    """Fetch all reviews from API, INSERT OR REPLACE into reviews table."""
    now = datetime.now(tz=timezone.utc)
    offset = 0
    count = 0
    while True:
        resp = api.get_reviews_by_shop(shop_id, limit=LIMIT, offset=offset)
        results = resp.get("results", [])
        total = resp.get("count", 0)
        for rev in results:
            con.execute(
                """
                INSERT OR REPLACE INTO reviews
                    (review_id, shop_id, listing_id, rating, review, language,
                     create_timestamp, update_timestamp, pulled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    rev.get("transaction_id"),
                    shop_id,
                    rev.get("listing_id"),
                    rev.get("rating"),
                    rev.get("review", ""),
                    rev.get("language", ""),
                    _ts_to_datetime(rev.get("create_timestamp")),
                    _ts_to_datetime(rev.get("update_timestamp")),
                    now,
                ],
            )
            count += 1

        if offset + LIMIT >= total:
            break
        offset += LIMIT
        print(f"Fetched {count}/{total} reviews...", file=sys.stderr)

    return count


def pull_stats_command(
    include_receipts: bool = typer.Option(
        False, "--include-receipts", help="Also pull receipts, transactions, and ledger entries"
    ),
) -> None:
    """Pull shop stats and listing snapshots directly from the Etsy API into DuckDB."""
    api = _get_api()
    shop_id = int(settings.shop_id)
    data_dir = get_data_dir()

    con = connect_db(data_dir)
    try:
        count = pull_listing_stats(api, shop_id, con)
        typer.echo(f"Snapshotted {count} listings.")

        pull_shop_stats(api, shop_id, con)
        typer.echo(f"Snapshotted shop {shop_id}.")

        if include_receipts:
            receipt_count = pull_receipts(api, shop_id, con)
            typer.echo(f"Pulled {receipt_count} receipts.")

            compute_revenue_summary(con, shop_id)
            typer.echo("Computed revenue summary.")

            txn_count = pull_transactions(api, shop_id, con)
            typer.echo(f"Pulled {txn_count} transactions.")

            ledger_count = pull_ledger(api, shop_id, con)
            typer.echo(f"Pulled {ledger_count} ledger entries.")
    finally:
        con.close()

    typer.echo(f"Analytics saved to {data_dir / 'analytics.db'}")


def pull_reviews_command() -> None:
    """Pull shop reviews from the Etsy API into DuckDB."""
    api = _get_api()
    shop_id = int(settings.shop_id)
    data_dir = get_data_dir()

    con = connect_db(data_dir)
    try:
        count = pull_reviews(api, shop_id, con)
        typer.echo(f"Pulled {count} reviews.")
    finally:
        con.close()

    typer.echo(f"Analytics saved to {data_dir / 'analytics.db'}")
