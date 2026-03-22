from pathlib import Path

import duckdb
import pytest

from etsync.analytics.schema import (
    CURRENT_SCHEMA_VERSION,
    _get_schema_version,
    connect_db,
)


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    return tmp_path


class TestConnectDbFresh:
    """Fresh database — no prior tables."""

    def test_creates_all_tables(self, db_dir: Path):
        con = connect_db(db_dir)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        con.close()
        expected = {
            "schema_version",
            "listing_snapshots",
            "shop_snapshots",
            "receipts",
            "revenue_summary",
            "transactions",
            "ledger_entries",
            "reviews",
        }
        assert expected == tables

    def test_schema_version_is_current(self, db_dir: Path):
        con = connect_db(db_dir)
        version = _get_schema_version(con)
        con.close()
        assert version == CURRENT_SCHEMA_VERSION

    def test_listing_snapshots_has_v2_columns(self, db_dir: Path):
        con = connect_db(db_dir)
        cols = {row[0] for row in con.execute("DESCRIBE listing_snapshots").fetchall()}
        con.close()
        assert "tags" in cols
        assert "taxonomy_path" in cols
        assert "featured_rank" in cols

    def test_shop_snapshots_has_v2_columns(self, db_dir: Path):
        con = connect_db(db_dir)
        cols = {row[0] for row in con.execute("DESCRIBE shop_snapshots").fetchall()}
        con.close()
        assert "num_favorers" in cols
        assert "currency_code" in cols


class TestMigrationFromV1:
    """Database with v1 tables already present (simulating existing data)."""

    def _create_v1_db(self, db_dir: Path) -> None:
        """Manually create v1 tables without schema_version tracking."""
        con = duckdb.connect(str(db_dir / "analytics.db"))
        con.execute("""
            CREATE TABLE listing_snapshots (
                listing_id BIGINT, title VARCHAR, views INTEGER, favorites INTEGER,
                price_amount DOUBLE, price_currency VARCHAR, quantity INTEGER,
                state VARCHAR, snapshot_date DATE
            )
        """)
        con.execute("""
            CREATE TABLE shop_snapshots (
                shop_id BIGINT, num_listings INTEGER, snapshot_date DATE
            )
        """)
        # Insert some v1 data
        con.execute("INSERT INTO listing_snapshots VALUES (1001, 'Mug', 50, 5, 25.0, 'EUR', 3, 'active', '2026-03-20')")
        con.execute("INSERT INTO shop_snapshots VALUES (123, 10, '2026-03-20')")
        con.close()

    def test_preserves_existing_data(self, db_dir: Path):
        self._create_v1_db(db_dir)
        con = connect_db(db_dir)
        rows = con.execute("SELECT * FROM listing_snapshots").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1001  # listing_id preserved
        con.close()

    def test_adds_new_columns(self, db_dir: Path):
        self._create_v1_db(db_dir)
        con = connect_db(db_dir)
        cols = {row[0] for row in con.execute("DESCRIBE listing_snapshots").fetchall()}
        assert "tags" in cols
        assert "featured_rank" in cols
        con.close()

    def test_creates_new_tables(self, db_dir: Path):
        self._create_v1_db(db_dir)
        con = connect_db(db_dir)
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert "receipts" in tables
        assert "reviews" in tables
        con.close()

    def test_version_is_current(self, db_dir: Path):
        self._create_v1_db(db_dir)
        con = connect_db(db_dir)
        assert _get_schema_version(con) == CURRENT_SCHEMA_VERSION
        con.close()


class TestIdempotency:
    def test_connect_twice_is_safe(self, db_dir: Path):
        con1 = connect_db(db_dir)
        con1.close()
        con2 = connect_db(db_dir)
        assert _get_schema_version(con2) == CURRENT_SCHEMA_VERSION
        tables = {row[0] for row in con2.execute("SHOW TABLES").fetchall()}
        assert "receipts" in tables
        con2.close()
