from pathlib import Path
from unittest.mock import MagicMock

import duckdb
import pytest

from etsync.analytics.pull import pull_reviews
from etsync.analytics.schema import connect_db


@pytest.fixture
def db_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def con(db_dir: Path):
    connection = connect_db(db_dir)
    yield connection
    connection.close()


def _make_review(review_id: int, rating: int = 5, listing_id: int = 1001) -> dict:
    return {
        "transaction_id": review_id,
        "listing_id": listing_id,
        "rating": rating,
        "review": f"Great product #{review_id}!",
        "language": "en",
        "create_timestamp": 1740000000 + review_id,
        "update_timestamp": 1740000000 + review_id,
    }


class TestPullReviews:
    def test_inserts_reviews(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_reviews_by_shop.return_value = {
            "count": 3,
            "results": [_make_review(1, 5), _make_review(2, 4), _make_review(3, 5)],
        }
        count = pull_reviews(api, 123, con)
        assert count == 3

        rows = con.execute("SELECT COUNT(*) FROM reviews").fetchone()
        assert rows is not None
        assert rows[0] == 3

    def test_replaces_on_duplicate(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_reviews_by_shop.return_value = {
            "count": 1,
            "results": [_make_review(1, rating=4)],
        }
        pull_reviews(api, 123, con)

        # Pull again with updated rating
        api.get_reviews_by_shop.return_value = {
            "count": 1,
            "results": [_make_review(1, rating=5)],
        }
        pull_reviews(api, 123, con)

        rows = con.execute("SELECT COUNT(*) FROM reviews").fetchone()
        assert rows is not None
        assert rows[0] == 1
        rating = con.execute("SELECT rating FROM reviews WHERE review_id = 1").fetchone()
        assert rating is not None
        assert rating[0] == 5

    def test_pagination(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        page1 = {"count": 150, "results": [_make_review(i) for i in range(100)]}
        page2 = {"count": 150, "results": [_make_review(i) for i in range(100, 150)]}
        api.get_reviews_by_shop.side_effect = [page1, page2]

        count = pull_reviews(api, 123, con)
        assert count == 150
        assert api.get_reviews_by_shop.call_count == 2

    def test_stores_all_fields(self, con: duckdb.DuckDBPyConnection):
        api = MagicMock()
        api.get_reviews_by_shop.return_value = {
            "count": 1,
            "results": [_make_review(42, rating=3, listing_id=2002)],
        }
        pull_reviews(api, 123, con)

        row = con.execute("SELECT review_id, shop_id, listing_id, rating, review, language FROM reviews").fetchone()
        assert row is not None
        assert row[0] == 42
        assert row[1] == 123
        assert row[2] == 2002
        assert row[3] == 3
        assert "Great product" in row[4]
        assert row[5] == "en"
