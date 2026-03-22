import json
from pathlib import Path

from etsync.listings.pull import _build_index_entry, _fetch_all_listings, _save_index, _save_listing


def _fake_listing(listing_id: int, title: str = "Test item") -> dict:
    return {
        "listing_id": listing_id,
        "title": title,
        "state": "active",
        "creation_timestamp": 1699000000,
        "last_modified_timestamp": 1700000000,
        "price": {"amount": 1000, "divisor": 100, "currency_code": "EUR"},
        "tags": ["metal", "art"],
        "quantity": 3,
    }


class FakeAPI:
    """Minimal stand-in for EtsyAPI that returns canned responses."""

    def __init__(self, pages: list[dict]):
        self._pages = pages
        self._call_count = 0

    def get_listings_by_shop(self, shop_id: int, limit: int = 100, offset: int = 0) -> dict:
        page = self._pages[self._call_count]
        self._call_count += 1
        return page


# --- _save_listing ---


def test_save_listing_writes_json(tmp_path: Path):
    listing = _fake_listing(42, "Widget")
    _save_listing(tmp_path, listing)
    path = tmp_path / "42" / "listing.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["listing_id"] == 42
    assert data["title"] == "Widget"


def test_save_listing_preserves_nested_data(tmp_path: Path):
    listing = _fake_listing(99, "Gadget")
    _save_listing(tmp_path, listing)
    data = json.loads((tmp_path / "99" / "listing.json").read_text())
    assert data["price"]["amount"] == 1000
    assert data["price"]["currency_code"] == "EUR"


def test_save_listing_preserves_nulls(tmp_path: Path):
    listing = _fake_listing(7, "Nullish")
    listing["description"] = None
    _save_listing(tmp_path, listing)
    data = json.loads((tmp_path / "7" / "listing.json").read_text())
    assert data["description"] is None


# --- _build_index_entry ---


def test_index_entry_basic_fields():
    entry = _build_index_entry(_fake_listing(42, "Widget"))
    assert entry["listing_id"] == 42
    assert entry["title"] == "Widget"
    assert entry["state"] == "active"
    assert entry["updated_timestamp"] == 1700000000


def test_index_entry_url():
    entry = _build_index_entry(_fake_listing(42))
    assert entry["url"] == "https://www.etsy.com/listing/42"


def test_index_entry_price():
    entry = _build_index_entry(_fake_listing(42))
    assert entry["price"]["amount"] == 1000
    assert entry["price"]["currency"] == "EUR"


def test_index_entry_tags_and_quantity():
    entry = _build_index_entry(_fake_listing(42))
    assert entry["tags"] == ["metal", "art"]
    assert entry["quantity"] == 3


def test_index_entry_creation_timestamp():
    entry = _build_index_entry(_fake_listing(42))
    assert entry["creation_timestamp"] == 1699000000


# --- _save_index ---


def test_save_index(tmp_path: Path):
    listings = [_fake_listing(1, "A"), _fake_listing(2, "B")]
    _save_index(tmp_path, listings, "2026-03-21T10:00:00+00:00")
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["count"] == 2
    assert index["synced_at"] == "2026-03-21T10:00:00+00:00"
    assert len(index["listings"]) == 2
    assert index["listings"][0]["listing_id"] == 1
    assert index["listings"][1]["title"] == "B"


def test_save_index_empty(tmp_path: Path):
    _save_index(tmp_path, [], "2026-03-21T10:00:00+00:00")
    index = json.loads((tmp_path / "index.json").read_text())
    assert index["listings"] == []
    assert index["count"] == 0


# --- _fetch_all_listings ---


def test_fetch_all_listings_single_page():
    listings = [_fake_listing(i) for i in range(5)]
    api = FakeAPI([{"count": 5, "results": listings}])
    result = _fetch_all_listings(api, shop_id=123)
    assert len(result) == 5
    assert api._call_count == 1


def test_fetch_all_listings_pagination():
    page1 = [_fake_listing(i) for i in range(100)]
    page2 = [_fake_listing(i) for i in range(100, 130)]
    api = FakeAPI(
        [
            {"count": 130, "results": page1},
            {"count": 130, "results": page2},
        ]
    )
    result = _fetch_all_listings(api, shop_id=123)
    assert len(result) == 130
    assert api._call_count == 2


def test_fetch_all_listings_empty():
    api = FakeAPI([{"count": 0, "results": []}])
    result = _fetch_all_listings(api, shop_id=123)
    assert result == []
    assert api._call_count == 1
