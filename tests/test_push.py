import json
from pathlib import Path

from etsync.listings.push import (
    FieldChange,
    ListingDiff,
    _format_diff,
    _load_local_listings,
    _normalize_value,
    diff_listing,
    validate_listing,
)


def _fake_listing(listing_id: int, **overrides: object) -> dict:
    base = {
        "listing_id": listing_id,
        "title": "Test item",
        "description": "A test description",
        "state": "active",
        "tags": ["metal", "art"],
        "quantity": 3,
        "who_made": "i_did",
        "when_made": "2020_2025",
        "taxonomy_id": 123,
        "price": {"amount": 1000, "divisor": 100, "currency_code": "EUR"},
    }
    base.update(overrides)
    return base


def _write_listing_nested(listings_dir: Path, listing: dict) -> None:
    lid = listing["listing_id"]
    d = listings_dir / str(lid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "listing.json").write_text(json.dumps(listing) + "\n")


def _write_listing_flat(listings_dir: Path, listing: dict) -> None:
    lid = listing["listing_id"]
    (listings_dir / f"{lid}.json").write_text(json.dumps(listing) + "\n")


# --- _normalize_value ---


class TestNormalizeValue:
    def test_sorts_lists(self):
        assert _normalize_value(["b", "a"]) == ["a", "b"]

    def test_passthrough_string(self):
        assert _normalize_value("hello") == "hello"

    def test_passthrough_int(self):
        assert _normalize_value(42) == 42

    def test_none(self):
        assert _normalize_value(None) is None


# --- diff_listing ---


class TestDiffListing:
    def test_no_changes(self):
        listing = _fake_listing(42)
        diff = diff_listing(listing, listing.copy())
        assert diff.changes == []
        assert diff.listing_id == 42

    def test_title_changed(self):
        local = _fake_listing(42, title="New title")
        remote = _fake_listing(42, title="Old title")
        diff = diff_listing(local, remote)
        assert len(diff.changes) == 1
        assert diff.changes[0].field == "title"
        assert diff.changes[0].old_value == "Old title"
        assert diff.changes[0].new_value == "New title"

    def test_tags_order_ignored(self):
        local = _fake_listing(42, tags=["art", "metal"])
        remote = _fake_listing(42, tags=["metal", "art"])
        diff = diff_listing(local, remote)
        assert diff.changes == []

    def test_tags_content_changed(self):
        local = _fake_listing(42, tags=["metal", "art", "new"])
        remote = _fake_listing(42, tags=["metal", "art"])
        diff = diff_listing(local, remote)
        assert len(diff.changes) == 1
        assert diff.changes[0].field == "tags"

    def test_multiple_changes(self):
        local = _fake_listing(42, title="New", description="Updated desc")
        remote = _fake_listing(42, title="Old", description="Old desc")
        diff = diff_listing(local, remote)
        changed_fields = {c.field for c in diff.changes}
        assert changed_fields == {"title", "description"}

    def test_skips_non_updatable_fields(self):
        local = _fake_listing(42, views=999)
        remote = _fake_listing(42, views=0)
        diff = diff_listing(local, remote)
        assert diff.changes == []

    def test_field_missing_in_local_skipped(self):
        local = {"listing_id": 42, "title": "Same"}
        remote = _fake_listing(42, title="Same")
        diff = diff_listing(local, remote)
        assert diff.changes == []


# --- _format_diff ---


class TestFormatDiff:
    def test_format_single_change(self):
        diff = ListingDiff(
            listing_id=42,
            title="Widget",
            changes=[FieldChange(field="title", old_value="Old", new_value="New")],
        )
        output = _format_diff(diff)
        assert "42" in output
        assert "Widget" in output
        assert "title" in output
        assert "'Old'" in output
        assert "'New'" in output

    def test_format_no_changes(self):
        diff = ListingDiff(listing_id=42, title="Widget", changes=[])
        output = _format_diff(diff)
        assert "42" in output
        assert "\n" not in output  # just the header line


# --- _load_local_listings ---


class TestLoadLocalListings:
    def test_loads_nested(self, tmp_path: Path):
        listing = _fake_listing(42)
        _write_listing_nested(tmp_path, listing)
        result = _load_local_listings(tmp_path)
        assert len(result) == 1
        assert result[0]["listing_id"] == 42

    def test_loads_flat(self, tmp_path: Path):
        listing = _fake_listing(42)
        _write_listing_flat(tmp_path, listing)
        result = _load_local_listings(tmp_path)
        assert len(result) == 1
        assert result[0]["listing_id"] == 42

    def test_prefers_nested_over_flat(self, tmp_path: Path):
        _write_listing_nested(tmp_path, _fake_listing(42, title="Nested"))
        _write_listing_flat(tmp_path, _fake_listing(42, title="Flat"))
        result = _load_local_listings(tmp_path)
        assert len(result) == 1
        assert result[0]["title"] == "Nested"

    def test_loads_by_id_nested(self, tmp_path: Path):
        _write_listing_nested(tmp_path, _fake_listing(42))
        _write_listing_nested(tmp_path, _fake_listing(99))
        result = _load_local_listings(tmp_path, listing_id=42)
        assert len(result) == 1
        assert result[0]["listing_id"] == 42

    def test_loads_by_id_flat(self, tmp_path: Path):
        _write_listing_flat(tmp_path, _fake_listing(42))
        result = _load_local_listings(tmp_path, listing_id=42)
        assert len(result) == 1

    def test_skips_index_json(self, tmp_path: Path):
        _write_listing_nested(tmp_path, _fake_listing(42))
        (tmp_path / "index.json").write_text('{"listings": []}')
        result = _load_local_listings(tmp_path)
        assert len(result) == 1

    def test_empty_dir(self, tmp_path: Path):
        result = _load_local_listings(tmp_path)
        assert result == []

    def test_missing_id_exits(self, tmp_path: Path):
        from click.exceptions import Exit

        import pytest

        with pytest.raises(Exit):
            _load_local_listings(tmp_path, listing_id=999)


# --- validate_listing ---


class TestValidateListing:
    def test_valid_listing(self):
        listing = _fake_listing(42, title="Short title", tags=["metal", "art"])
        assert validate_listing(listing) == []

    def test_tag_too_long(self):
        listing = {"tags": ["short", "this tag is way too long for etsy"]}
        errors = validate_listing(listing)
        assert len(errors) == 1
        assert errors[0].field == "tags"
        assert "this tag is way too long for etsy" in errors[0].message

    def test_multiple_tags_too_long(self):
        listing = {"tags": ["exactly twenty chars!", "also exceeds the limit!"]}
        errors = validate_listing(listing)
        assert len(errors) == 2

    def test_title_too_long(self):
        listing = {"title": "x" * 141}
        errors = validate_listing(listing)
        assert len(errors) == 1
        assert errors[0].field == "title"

    def test_title_at_limit(self):
        listing = {"title": "x" * 140}
        assert validate_listing(listing) == []

    def test_tag_at_limit(self):
        listing = {"tags": ["x" * 20]}
        assert validate_listing(listing) == []

    def test_too_many_tags(self):
        listing = {"tags": [f"tag{i}" for i in range(14)]}
        errors = validate_listing(listing)
        assert len(errors) == 1
        assert "more than 13" in errors[0].message

    def test_no_tags_or_title(self):
        listing = {"description": "Just a description"}
        assert validate_listing(listing) == []
