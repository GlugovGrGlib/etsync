"""Fetch shop stats and listing snapshots, store in DuckDB for time-series analysis."""

import json
from datetime import date
from pathlib import Path

import duckdb
import typer

from etsync.config import get_data_dir, settings


def _ensure_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create analytics tables if they don't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS listing_snapshots (
            listing_id   BIGINT,
            title        VARCHAR,
            views        INTEGER,
            favorites    INTEGER,
            price_amount DOUBLE,
            price_currency VARCHAR,
            quantity     INTEGER,
            state        VARCHAR,
            snapshot_date DATE
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS shop_snapshots (
            shop_id       BIGINT,
            num_listings  INTEGER,
            snapshot_date DATE
        )
    """)


def _get_db_path(data_dir: Path | None = None) -> Path:
    if data_dir is None:
        data_dir = get_data_dir()
    return data_dir / "analytics.db"


def snapshot_listings(con: duckdb.DuckDBPyConnection, listings_dir: Path, snapshot_dt: date) -> int:
    """Read pulled listing JSON files and insert snapshot rows."""
    count = 0
    for json_path in sorted(listings_dir.glob("*.json")):
        if json_path.name == "index.json":
            continue
        listing = json.loads(json_path.read_text())

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

        con.execute(
            """
            INSERT INTO listing_snapshots
                (listing_id, title, views, favorites, price_amount, price_currency, quantity, state, snapshot_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [listing_id, title, views, favorites, price_amount, price_currency, quantity, state, snapshot_dt],
        )
        count += 1

    return count


def snapshot_shop(con: duckdb.DuckDBPyConnection, shop_id: int, num_listings: int, snapshot_dt: date) -> None:
    """Insert a shop snapshot row."""
    con.execute(
        "INSERT INTO shop_snapshots (shop_id, num_listings, snapshot_date) VALUES (?, ?, ?)",
        [shop_id, num_listings, snapshot_dt],
    )


def pull_stats() -> None:
    """Snapshot listing stats into DuckDB for analytics."""
    from etsync.listings.pull import _get_api

    data_dir = get_data_dir()
    db_path = _get_db_path(data_dir)
    listings_dir = data_dir / "listings"

    if not listings_dir.exists():
        typer.echo("No listings directory found. Run 'etsync pull listings' first.", err=True)
        raise typer.Exit(code=1)

    api = _get_api()
    shop_id = int(settings.shop_id)
    today = date.today()

    shop_info = api.get_shop(shop_id=shop_id)
    num_listings = shop_info.get("listing_active_count", 0)

    con = duckdb.connect(str(db_path))
    try:
        _ensure_tables(con)
        count = snapshot_listings(con, listings_dir, today)
        typer.echo(f"Snapshotted {count} listings.")
        snapshot_shop(con, shop_id, num_listings, today)
        typer.echo(f"Snapshotted shop {shop_id} with {num_listings} active listings.")
    finally:
        con.close()

    typer.echo(f"Analytics saved to {db_path}")
