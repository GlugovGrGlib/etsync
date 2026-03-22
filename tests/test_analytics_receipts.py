from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from etsync.analytics.pull import (
    compute_revenue_summary,
    pull_ledger,
    pull_receipts,
    pull_transactions,
)
from etsync.analytics.schema import connect_db


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def con(db_dir: Path):
    connection = connect_db(db_dir)
    yield connection
    connection.close()


def _make_receipt(receipt_id: int, grandtotal: int, was_paid: bool = True, ts: int = 1740000000) -> dict:
    return {
        "receipt_id": receipt_id,
        "buyer_email": "buyer@example.com",
        "formatted_address": {"country_iso": "DE"},
        "grandtotal": {"amount": grandtotal, "currency_code": "EUR"},
        "subtotal": {"amount": grandtotal - 200, "currency_code": "EUR"},
        "total_shipping_cost": {"amount": 500, "currency_code": "EUR"},
        "total_tax_cost": {"amount": 200, "currency_code": "EUR"},
        "status": "paid" if was_paid else "open",
        "was_paid": was_paid,
        "was_shipped": False,
        "create_timestamp": ts,
        "update_timestamp": ts,
    }


def _make_transaction(txn_id: int, receipt_id: int, listing_id: int, qty: int = 1, price: int = 2500) -> dict:
    return {
        "transaction_id": txn_id,
        "receipt_id": receipt_id,
        "listing_id": listing_id,
        "title": f"Item {listing_id}",
        "quantity": qty,
        "price": {"amount": price, "currency_code": "EUR"},
        "shipping_cost": {"amount": 500, "currency_code": "EUR"},
        "create_timestamp": 1740000000,
    }


def _make_ledger_entry(entry_id: int, amount: int = 1000) -> dict:
    return {
        "entry_id": entry_id,
        "amount": {"amount": amount, "currency_code": "EUR"},
        "entry_type": "payment",
        "description": "Order payment",
        "ledger_type": "credit",
        "create_date": 1740000000,
    }


class TestPullReceipts:
    def test_inserts_receipts(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_receipts.return_value = {
            "count": 2,
            "results": [_make_receipt(1, 5000), _make_receipt(2, 7500)],
        }
        count = pull_receipts(api, 123, con)
        assert count == 2
        rows = con.execute("SELECT COUNT(*) FROM receipts").fetchone()
        assert rows is not None
        assert rows[0] == 2

    def test_replaces_on_duplicate(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_receipts.return_value = {
            "count": 1,
            "results": [_make_receipt(1, 5000, was_paid=False)],
        }
        pull_receipts(api, 123, con)

        api.get_shop_receipts.return_value = {
            "count": 1,
            "results": [_make_receipt(1, 5000, was_paid=True)],
        }
        pull_receipts(api, 123, con)

        rows = con.execute("SELECT COUNT(*) FROM receipts").fetchone()
        assert rows is not None
        assert rows[0] == 1
        paid = con.execute("SELECT was_paid FROM receipts WHERE receipt_id = 1").fetchone()
        assert paid is not None
        assert paid[0] is True

    def test_pagination(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        page1 = {"count": 150, "results": [_make_receipt(i, 1000) for i in range(100)]}
        page2 = {
            "count": 150,
            "results": [_make_receipt(i, 1000) for i in range(100, 150)],
        }
        api.get_shop_receipts.side_effect = [page1, page2]

        count = pull_receipts(api, 123, con)
        assert count == 150
        assert api.get_shop_receipts.call_count == 2


class TestComputeRevenueSummary:
    def test_monthly_aggregation(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        jan_ts = int(datetime(2026, 1, 15, tzinfo=timezone.utc).timestamp())
        feb_ts = int(datetime(2026, 2, 10, tzinfo=timezone.utc).timestamp())
        api.get_shop_receipts.return_value = {
            "count": 3,
            "results": [
                _make_receipt(1, 5000, ts=jan_ts),
                _make_receipt(2, 7500, ts=jan_ts),
                _make_receipt(3, 12000, ts=feb_ts),
            ],
        }
        pull_receipts(api, 123, con)
        compute_revenue_summary(con, 123)

        rows = con.execute(
            "SELECT period_start, total_receipts, total_revenue FROM revenue_summary ORDER BY period_start"
        ).fetchall()
        assert len(rows) == 2
        assert rows[0][1] == 2  # 2 receipts in Jan
        assert rows[0][2] == 12500  # 5000 + 7500
        assert rows[1][1] == 1  # 1 receipt in Feb
        assert rows[1][2] == 12000

    def test_excludes_unpaid_receipts(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_receipts.return_value = {
            "count": 2,
            "results": [
                _make_receipt(1, 5000, was_paid=True),
                _make_receipt(2, 7500, was_paid=False),
            ],
        }
        pull_receipts(api, 123, con)
        compute_revenue_summary(con, 123)

        rows = con.execute("SELECT total_receipts, total_revenue FROM revenue_summary").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == 1
        assert rows[0][1] == 5000


class TestPullTransactions:
    def test_inserts_transactions(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_receipt_transactions_by_shop.return_value = {
            "count": 2,
            "results": [
                _make_transaction(1, 10, 1001, qty=1),
                _make_transaction(2, 10, 1002, qty=3),
            ],
        }
        count = pull_transactions(api, 123, con)
        assert count == 2

    def test_replaces_on_duplicate(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_receipt_transactions_by_shop.return_value = {
            "count": 1,
            "results": [_make_transaction(1, 10, 1001, qty=1)],
        }
        pull_transactions(api, 123, con)
        pull_transactions(api, 123, con)

        rows = con.execute("SELECT COUNT(*) FROM transactions").fetchone()
        assert rows is not None
        assert rows[0] == 1


class TestPullLedger:
    def test_inserts_entries(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_payment_account_ledger_entries.return_value = {
            "count": 2,
            "results": [_make_ledger_entry(1, 1000), _make_ledger_entry(2, 2000)],
        }
        count = pull_ledger(api, 123, con)
        assert count == 2

    def test_replaces_on_duplicate(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_shop_payment_account_ledger_entries.return_value = {
            "count": 1,
            "results": [_make_ledger_entry(1, 1000)],
        }
        pull_ledger(api, 123, con)
        pull_ledger(api, 123, con)

        rows = con.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()
        assert rows is not None
        assert rows[0] == 1
