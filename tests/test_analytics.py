from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from etsync.analytics.pull import pull_listing_stats, pull_shop_stats
from etsync.analytics.query import format_table, run_query
from etsync.analytics.schema import connect_db


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def db_path(db_dir: Path) -> Path:
    return db_dir / "analytics.db"


@pytest.fixture
def con(db_dir: Path):
    connection = connect_db(db_dir)
    yield connection
    connection.close()


def _make_listing(listing_id: int, title: str, views: int, favorites: int, price: int = 2500) -> dict:
    return {
        "listing_id": listing_id,
        "title": title,
        "views": views,
        "num_favorers": favorites,
        "price": {"amount": price, "currency_code": "EUR"},
        "quantity": 5,
        "state": "active",
        "tags": ["handmade", "gift"],
        "taxonomy_path": ["Art", "Sculpture"],
        "creation_timestamp": 1700000000,
        "last_modified_timestamp": 1740000000,
        "featured_rank": None,
    }


def _make_api_with_listings(listings: list[dict]) -> MagicMock:
    api = MagicMock()
    api.get_listings_by_shop.return_value = {
        "count": len(listings),
        "results": listings,
    }
    return api


class TestPullListingStats:
    def test_inserts_from_api(self, con: duckdb.DuckDBPyConnection):
        listings = [_make_listing(1001, "Mug", 150, 12), _make_listing(1002, "Spoon", 80, 4)]
        api = _make_api_with_listings(listings)

        count = pull_listing_stats(api, 123, con)
        assert count == 2
        rows = con.execute("SELECT * FROM listing_snapshots ORDER BY listing_id").fetchall()
        assert len(rows) == 2
        assert rows[0][0] == 1001
        assert rows[0][4] == 25.0  # 2500 cents -> 25.00

    def test_captures_v2_fields(self, con: duckdb.DuckDBPyConnection):
        api = _make_api_with_listings([_make_listing(1001, "Mug", 150, 12)])
        pull_listing_stats(api, 123, con)

        row = con.execute("SELECT tags, taxonomy_path FROM listing_snapshots WHERE listing_id = 1001").fetchone()
        assert row is not None
        assert row[0] == ["handmade", "gift"]
        assert row[1] == ["Art", "Sculpture"]

    def test_empty_response(self, con: duckdb.DuckDBPyConnection):
        api = _make_api_with_listings([])
        count = pull_listing_stats(api, 123, con)
        assert count == 0

    def test_appends_snapshots(self, con: duckdb.DuckDBPyConnection):
        api = _make_api_with_listings([_make_listing(1001, "Mug", 150, 12)])
        pull_listing_stats(api, 123, con)
        pull_listing_stats(api, 123, con)
        rows = con.execute("SELECT COUNT(*) FROM listing_snapshots").fetchone()
        assert rows is not None
        assert rows[0] == 2


class TestPullShopStats:
    def test_inserts_shop_snapshot(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop.return_value = {
            "listing_active_count": 42,
            "num_favorers": 100,
            "digital_listing_count": 5,
            "currency_code": "EUR",
            "login_name": "TestShop",
        }
        pull_shop_stats(api, 123, con)
        rows = con.execute("SELECT * FROM shop_snapshots").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 123  # shop_id
        assert rows[0][1] == 42  # num_listings

    def test_captures_v2_fields(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop.return_value = {
            "listing_active_count": 42,
            "num_favorers": 100,
            "digital_listing_count": 5,
            "currency_code": "EUR",
            "login_name": "TestShop",
        }
        pull_shop_stats(api, 123, con)
        row = con.execute("SELECT num_favorers, currency_code, login_name FROM shop_snapshots").fetchone()
        assert row is not None
        assert row[0] == 100
        assert row[1] == "EUR"
        assert row[2] == "TestShop"


class TestRunQuery:
    def test_select(self, db_path: Path, con: duckdb.DuckDBPyConnection):
        api = _make_api_with_listings([_make_listing(1001, "Mug", 150, 12)])
        pull_listing_stats(api, 123, con)
        con.close()
        columns, rows = run_query(db_path, "SELECT listing_id, title FROM listing_snapshots ORDER BY listing_id")
        assert columns == ["listing_id", "title"]
        assert len(rows) == 1
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
