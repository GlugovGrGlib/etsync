"""Query helpers and pre-built analytics commands for the DuckDB database."""

from pathlib import Path

import duckdb
import typer

from etsync.analytics.schema import connect_db


def run_query(db_path: Path, sql: str) -> tuple[list[str], list[tuple[object, ...]]]:
    """Open the DuckDB and execute a SQL query. Returns (columns, rows)."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result = con.execute(sql)
        columns: list[str] = [desc[0] for desc in result.description]
        rows: list[tuple[object, ...]] = result.fetchall()
    finally:
        con.close()
    return columns, rows


def format_table(columns: list[str], rows: list[tuple[object, ...]]) -> str:
    """Format query results as a simple text table."""
    if not rows:
        return "(no results)"

    str_rows = [[str(v) for v in row] for row in rows]
    widths = [max(len(col), *(len(r[i]) for r in str_rows)) for i, col in enumerate(columns)]

    header = " | ".join(col.ljust(w) for col, w in zip(columns, widths))
    separator = "-+-".join("-" * w for w in widths)
    body_lines = [" | ".join(val.ljust(w) for val, w in zip(row, widths)) for row in str_rows]

    return "\n".join([header, separator, *body_lines])


def _format_currency(amount_cents: int | None, currency: str = "") -> str:
    """Format an amount in smallest currency unit to a readable string."""
    if amount_cents is None:
        return "—"
    return f"{currency} {amount_cents / 100:.2f}".strip()


def _get_analytics_con(data_dir: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the analytics DB for query commands, with helpful error on missing DB."""
    from etsync.config import get_data_dir

    if data_dir is None:
        data_dir = get_data_dir()
    db_path = data_dir / "analytics.db"
    if not db_path.exists():
        typer.echo(f"Analytics database not found at {db_path}. Run 'etsync pull stats' first.", err=True)
        raise typer.Exit(code=1)
    return connect_db(data_dir)


def query_command(sql: str = typer.Argument(help="SQL query to run against the analytics database")) -> None:
    """Run a SQL query against the analytics DuckDB."""
    from etsync.config import get_data_dir

    db_path = get_data_dir() / "analytics.db"
    if not db_path.exists():
        typer.echo(f"Analytics database not found at {db_path}. Run 'etsync pull stats' first.", err=True)
        raise typer.Exit(code=1)

    columns, rows = run_query(db_path, sql)
    typer.echo(format_table(columns, rows))


def top_listings_command(
    by: str = typer.Option("views", "--by", help="Sort by: views, favorites, or sales"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of listings to show"),
) -> None:
    """Show top performing listings from the most recent snapshot."""
    con = _get_analytics_con()
    try:
        # Check if any data exists
        row = con.execute("SELECT MAX(snapshot_date) FROM listing_snapshots").fetchone()
        if row is None or row[0] is None:
            typer.echo("No listing stats found. Run `etsync pull stats` first.")
            return

        latest_date = row[0]
        typer.echo(f"Snapshot date: {latest_date}\n")

        if by == "sales":
            # Join with transactions for sales data
            result = con.execute(
                """
                SELECT
                    ls.listing_id,
                    ls.title,
                    ls.views,
                    ls.favorites,
                    ls.price_amount,
                    ls.quantity,
                    COALESCE(t.units_sold, 0) AS units_sold
                FROM listing_snapshots ls
                LEFT JOIN (
                    SELECT listing_id, SUM(quantity) AS units_sold
                    FROM transactions
                    GROUP BY listing_id
                ) t ON ls.listing_id = t.listing_id
                WHERE ls.snapshot_date = ?
                ORDER BY units_sold DESC
                LIMIT ?
                """,
                [latest_date, limit],
            )
        else:
            order_col = "views" if by == "views" else "favorites"
            result = con.execute(
                f"""
                SELECT listing_id, title, views, favorites, price_amount, quantity
                FROM listing_snapshots
                WHERE snapshot_date = ?
                ORDER BY {order_col} DESC
                LIMIT ?
                """,
                [latest_date, limit],
            )

        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        typer.echo(format_table(columns, rows))
    finally:
        con.close()


def revenue_command() -> None:
    """Show monthly revenue summary from receipts."""
    con = _get_analytics_con()
    try:
        row = con.execute("SELECT COUNT(*) FROM revenue_summary").fetchone()
        if row is None or row[0] == 0:
            typer.echo("No revenue data. Run `etsync pull stats --include-receipts` first.")
            return

        result = con.execute("""
            SELECT
                strftime(period_start, '%Y-%m') AS month,
                total_receipts AS orders,
                total_revenue,
                total_shipping,
                total_tax,
                currency_code
            FROM revenue_summary
            ORDER BY period_start
        """)
        rows = result.fetchall()

        # Format amounts from cents to currency
        formatted_rows = []
        for row in rows:
            month, orders, revenue, shipping, tax, currency = row
            formatted_rows.append(
                (
                    month,
                    str(orders),
                    _format_currency(revenue, currency),
                    _format_currency(shipping, currency),
                    _format_currency(tax, currency),
                )
            )

        columns = ["month", "orders", "revenue", "shipping", "tax"]
        typer.echo(format_table(columns, formatted_rows))
    finally:
        con.close()


def reviews_command() -> None:
    """Show review summary — avg rating, distribution, recent reviews."""
    con = _get_analytics_con()
    try:
        row = con.execute("SELECT COUNT(*) FROM reviews").fetchone()
        if row is None or row[0] == 0:
            typer.echo("No reviews found. Run `etsync pull reviews` first.")
            return

        # Summary stats
        stats = con.execute("""
            SELECT COUNT(*) AS total, ROUND(AVG(rating), 2) AS avg_rating
            FROM reviews
        """).fetchone()
        assert stats is not None
        typer.echo(f"Total reviews: {stats[0]}  |  Average rating: {stats[1]}\n")

        # Rating distribution
        dist = con.execute("""
            SELECT rating, COUNT(*) AS count
            FROM reviews
            GROUP BY rating
            ORDER BY rating DESC
        """).fetchall()
        typer.echo("Rating distribution:")
        for rating, count in dist:
            bar = "*" * count
            typer.echo(f"  {rating}-star: {count:>4}  {bar}")
        typer.echo()

        # Recent reviews
        result = con.execute("""
            SELECT
                r.rating,
                COALESCE(ls.title, CAST(r.listing_id AS VARCHAR)) AS listing,
                CASE WHEN LENGTH(r.review) > 80
                     THEN SUBSTRING(r.review, 1, 80) || '...'
                     ELSE r.review END AS review_text
            FROM reviews r
            LEFT JOIN (
                SELECT listing_id, title,
                       ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY snapshot_date DESC) AS rn
                FROM listing_snapshots
            ) ls ON r.listing_id = ls.listing_id AND ls.rn = 1
            ORDER BY r.create_timestamp DESC
            LIMIT 5
        """)
        columns = [desc[0] for desc in result.description]
        rows = result.fetchall()
        typer.echo("Recent reviews:")
        typer.echo(format_table(columns, rows))
    finally:
        con.close()


def sales_command(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of listings to show"),
) -> None:
    """Show sales per listing from transaction data."""
    con = _get_analytics_con()
    try:
        row = con.execute("SELECT COUNT(*) FROM transactions").fetchone()
        if row is None or row[0] == 0:
            typer.echo("No sales data. Run `etsync pull stats --include-receipts` first.")
            return

        result = con.execute(
            """
            SELECT
                t.listing_id,
                COALESCE(ls.title, t.title) AS title,
                SUM(t.quantity) AS units_sold,
                SUM(t.price_amount) AS total_revenue,
                t.price_currency AS currency
            FROM transactions t
            LEFT JOIN (
                SELECT listing_id, title,
                       ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY snapshot_date DESC) AS rn
                FROM listing_snapshots
            ) ls ON t.listing_id = ls.listing_id AND ls.rn = 1
            GROUP BY t.listing_id, COALESCE(ls.title, t.title), t.price_currency
            ORDER BY units_sold DESC
            LIMIT ?
            """,
            [limit],
        )

        raw_rows = result.fetchall()
        formatted_rows = []
        for listing_id, title, units, revenue, currency in raw_rows:
            formatted_rows.append(
                (
                    str(listing_id),
                    title,
                    str(units),
                    _format_currency(revenue, currency),
                )
            )

        columns = ["listing_id", "title", "units_sold", "total_revenue"]
        typer.echo(format_table(columns, formatted_rows))
    finally:
        con.close()
