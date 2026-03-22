"""Schema definitions and versioned migrations for the analytics DuckDB database."""

from collections.abc import Callable
from pathlib import Path

import duckdb

CURRENT_SCHEMA_VERSION = 3


def _get_schema_version(con: duckdb.DuckDBPyConnection) -> int:
    """Read the current schema version, defaulting to 0 if no tracking table exists."""
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "schema_version" not in tables:
        return 0
    row = con.execute("SELECT MAX(version) FROM schema_version").fetchone()
    if row is None or row[0] is None:
        return 0
    return int(row[0])


def _set_schema_version(con: duckdb.DuckDBPyConnection, version: int) -> None:
    con.execute(
        "INSERT INTO schema_version (version, migrated_at) VALUES (?, current_timestamp)",
        [version],
    )


def _migrate_0_to_1(con: duckdb.DuckDBPyConnection) -> None:
    """Recognize existing tables as version 1, or create them fresh."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version     INTEGER NOT NULL,
            migrated_at TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
    """)
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
    _set_schema_version(con, 1)


def _migrate_1_to_2(con: duckdb.DuckDBPyConnection) -> None:
    """Add richer columns and new tables for receipts, transactions, ledger, reviews."""
    # Extend listing_snapshots
    con.execute("ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS tags VARCHAR[]")
    con.execute("ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS taxonomy_path VARCHAR[]")
    con.execute("ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS creation_tsz TIMESTAMP")
    con.execute("ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS last_modified_tsz TIMESTAMP")
    con.execute("ALTER TABLE listing_snapshots ADD COLUMN IF NOT EXISTS featured_rank INTEGER")

    # Extend shop_snapshots
    con.execute("ALTER TABLE shop_snapshots ADD COLUMN IF NOT EXISTS num_favorers INTEGER")
    con.execute("ALTER TABLE shop_snapshots ADD COLUMN IF NOT EXISTS digital_listing_count INTEGER")
    con.execute("ALTER TABLE shop_snapshots ADD COLUMN IF NOT EXISTS currency_code VARCHAR(3)")
    con.execute("ALTER TABLE shop_snapshots ADD COLUMN IF NOT EXISTS login_name VARCHAR")

    # New tables
    con.execute("""
        CREATE TABLE IF NOT EXISTS receipts (
            receipt_id        BIGINT NOT NULL PRIMARY KEY,
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
            pulled_at         TIMESTAMP NOT NULL
        )
    """)
    con.execute("""
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
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id    BIGINT NOT NULL PRIMARY KEY,
            receipt_id        BIGINT NOT NULL,
            listing_id        BIGINT NOT NULL,
            title             VARCHAR,
            quantity          INTEGER,
            price_amount      BIGINT,
            price_currency    VARCHAR(3),
            shipping_cost     BIGINT,
            create_timestamp  TIMESTAMP,
            pulled_at         TIMESTAMP NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ledger_entries (
            entry_id          BIGINT NOT NULL PRIMARY KEY,
            shop_id           BIGINT NOT NULL,
            amount            BIGINT,
            currency_code     VARCHAR(3),
            entry_type        VARCHAR,
            description       VARCHAR,
            ledger_type       VARCHAR,
            create_date       TIMESTAMP,
            pulled_at         TIMESTAMP NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            review_id         BIGINT NOT NULL PRIMARY KEY,
            shop_id           BIGINT NOT NULL,
            listing_id        BIGINT,
            rating            INTEGER,
            review            VARCHAR,
            language          VARCHAR,
            create_timestamp  TIMESTAMP,
            update_timestamp  TIMESTAMP,
            pulled_at         TIMESTAMP NOT NULL
        )
    """)
    _set_schema_version(con, 2)


def _migrate_2_to_3(con: duckdb.DuckDBPyConnection) -> None:
    """Add Etsy Ads tables: campaign snapshots, per-listing ad stats, and keyword data."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS ad_campaign_snapshots (
            snapshot_date     DATE NOT NULL,
            period_start      DATE NOT NULL,
            period_end        DATE NOT NULL,
            total_views       INTEGER,
            total_clicks      INTEGER,
            total_orders      INTEGER,
            total_revenue     DOUBLE,
            total_spend       DOUBLE,
            roas              DOUBLE,
            daily_budget      DOUBLE,
            strategy          VARCHAR,
            offsite_clicks    INTEGER,
            offsite_orders    INTEGER,
            PRIMARY KEY (snapshot_date, period_start)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ad_listing_snapshots (
            snapshot_date       DATE NOT NULL,
            period_start        DATE NOT NULL,
            period_end          DATE NOT NULL,
            listing_id          BIGINT NOT NULL,
            title               VARCHAR,
            ad_enabled          BOOLEAN,
            ad_views            INTEGER,
            ad_clicks           INTEGER,
            click_rate          DOUBLE,
            ad_orders           INTEGER,
            ad_revenue          DOUBLE,
            ad_spend            DOUBLE,
            roas                DOUBLE,
            lifetime_ad_orders  INTEGER,
            lifetime_ad_revenue DOUBLE,
            PRIMARY KEY (snapshot_date, period_start, listing_id)
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS ad_keywords (
            snapshot_date     DATE NOT NULL,
            period_start      DATE NOT NULL,
            period_end        DATE NOT NULL,
            listing_id        BIGINT NOT NULL,
            keyword           VARCHAR NOT NULL,
            roas              DOUBLE,
            orders            INTEGER,
            spend             DOUBLE,
            revenue           DOUBLE,
            clicks            INTEGER,
            click_rate        DOUBLE,
            views             INTEGER,
            is_relevant       BOOLEAN,
            PRIMARY KEY (snapshot_date, period_start, listing_id, keyword)
        )
    """)
    _set_schema_version(con, 3)


_MIGRATIONS: dict[int, Callable[[duckdb.DuckDBPyConnection], None]] = {
    0: _migrate_0_to_1,
    1: _migrate_1_to_2,
    2: _migrate_2_to_3,
}


def connect_db(data_dir: Path) -> duckdb.DuckDBPyConnection:
    """Open the analytics DuckDB, running any pending migrations."""
    db_path = data_dir / "analytics.db"
    con = duckdb.connect(str(db_path))
    version = _get_schema_version(con)
    while version < CURRENT_SCHEMA_VERSION:
        migration = _MIGRATIONS[version]
        migration(con)
        version = _get_schema_version(con)
    return con
