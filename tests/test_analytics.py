import json
from datetime import date
from pathlib import Path

import duckdb
import pytest

from etsync.analytics.pull import _ensure_tables, snapshot_listings, snapshot_shop
from etsync.analytics.query import format_table, run_query


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "analytics.db"


@pytest.fixture
def con(db_path: Path):
    connection = duckdb.connect(str(db_path))
    _ensure_tables(connection)
    yield connection
    connection.close()


@pytest.fixture
def listings_dir(tmp_path: Path) -> Path:
    d = tmp_path / "listings"
    d.mkdir()
    listing1 = {
        "listing_id": 1001,
        "title": "Handmade Mug",
        "views": 150,
        "num_favorers": 12,
        "price": {"amount": 2500, "currency_code": "EUR"},
        "quantity": 5,
        "state": "active",
    }
    listing2 = {
        "listing_id": 1002,
        "title": "Vintage Spoon",
        "views": 80,
        "num_favorers": 4,
        "price": {"amount": 1200, "currency_code": "EUR"},
        "quantity": 10,
        "state": "active",
    }
    for listing in [listing1, listing2]:
        (d / f"{listing['listing_id']}.json").write_text(json.dumps(listing))
    return d


class TestEnsureTables:
    def test_creates_tables(self, con: duckdb.DuckDBPyConnection):
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        assert "listing_snapshots" in tables
        assert "shop_snapshots" in tables

    def test_idempotent(self, con: duckdb.DuckDBPyConnection):
        _ensure_tables(con)
        assert len(con.execute("SHOW TABLES").fetchall()) == 2


class TestSnapshotListings:
    def test_inserts_rows(self, con: duckdb.DuckDBPyConnection, listings_dir: Path):
        count = snapshot_listings(con, listings_dir, date(2026, 3, 21))
        assert count == 2
        rows = con.execute("SELECT * FROM listing_snapshots ORDER BY listing_id").fetchall()
        assert len(rows) == 2
        assert rows[0][0] == 1001
        assert rows[0][4] == 25.0  # 2500 cents -> 25.00

    def test_appends_snapshots(self, con: duckdb.DuckDBPyConnection, listings_dir: Path):
        snapshot_listings(con, listings_dir, date(2026, 3, 20))
        snapshot_listings(con, listings_dir, date(2026, 3, 21))
        rows = con.execute("SELECT COUNT(*) FROM listing_snapshots").fetchone()
        assert rows is not None
        assert rows[0] == 4

    def test_empty_directory(self, con: duckdb.DuckDBPyConnection, tmp_path: Path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        assert snapshot_listings(con, empty_dir, date(2026, 3, 21)) == 0


class TestSnapshotShop:
    def test_inserts_row(self, con: duckdb.DuckDBPyConnection):
        snapshot_shop(con, shop_id=12345, num_listings=42, snapshot_dt=date(2026, 3, 21))
        rows = con.execute("SELECT * FROM shop_snapshots").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 12345
        assert rows[0][1] == 42


class TestRunQuery:
    def test_select(self, db_path: Path, con: duckdb.DuckDBPyConnection, listings_dir: Path):
        snapshot_listings(con, listings_dir, date(2026, 3, 21))
        con.close()
        columns, rows = run_query(db_path, "SELECT listing_id, title FROM listing_snapshots ORDER BY listing_id")
        assert columns == ["listing_id", "title"]
        assert len(rows) == 2
        assert rows[0][0] == 1001

    def test_empty_result(self, db_path: Path, con: duckdb.DuckDBPyConnection):
        con.close()
        columns, rows = run_query(db_path, "SELECT * FROM listing_snapshots")
        assert rows == []


class TestFormatTable:
    def test_formats_data(self):
        output = format_table(["id", "name"], [(1, "Alice"), (2, "Bob")])
        assert "Alice" in output
        assert "-+-" in output

    def test_empty(self):
        assert format_table(["a"], []) == "(no results)"
