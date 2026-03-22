import json
from pathlib import Path

import pytest

from etsync.listings.translations import (
    _diff_translation,
    _fetch_translation,
    _load_listing_ids,
    _load_local_translation,
    _save_translation,
    _scan_local_translations,
    pull_translations_for_listings,
)


def _fake_translation(listing_id: int, language: str) -> dict:
    return {
        "listing_id": listing_id,
        "language": language,
        "title": f"Title in {language}",
        "description": f"Description in {language}",
        "tags": [f"tag-{language}"],
    }


def _write_index(listings_dir: Path, listing_ids: list[int]) -> None:
    index = {
        "synced_at": "2026-03-21T10:00:00+00:00",
        "count": len(listing_ids),
        "listings": [{"listing_id": lid, "title": f"Listing {lid}"} for lid in listing_ids],
    }
    listings_dir.mkdir(parents=True, exist_ok=True)
    (listings_dir / "index.json").write_text(json.dumps(index) + "\n")


class FakeTranslationAPI:
    """Fake API that returns translations for specific (listing_id, language) pairs."""

    def __init__(self, translations: dict[tuple[int, str], dict]):
        self._translations = translations
        self.calls: list[tuple[int, str]] = []

    def get_listing_translation(self, shop_id: int, listing_id: int, language: str) -> dict:
        self.calls.append((listing_id, language))
        key = (listing_id, language)
        if key not in self._translations:
            raise Exception("404 Not Found")
        return self._translations[key]


# --- _load_listing_ids ---


class TestLoadListingIds:
    def test_loads_ids_from_index(self, tmp_path: Path):
        _write_index(tmp_path, [100, 200, 300])
        ids = _load_listing_ids(tmp_path)
        assert ids == [100, 200, 300]

    def test_no_index_exits(self, tmp_path: Path):
        from click.exceptions import Exit

        with pytest.raises(Exit):
            _load_listing_ids(tmp_path)

    def test_empty_index(self, tmp_path: Path):
        _write_index(tmp_path, [])
        ids = _load_listing_ids(tmp_path)
        assert ids == []


# --- _save_translation ---


class TestSaveTranslation:
    def test_saves_to_correct_path(self, tmp_path: Path):
        data = _fake_translation(42, "de")
        _save_translation(tmp_path, 42, "de", data)
        path = tmp_path / "42" / "translations" / "de.json"
        assert path.exists()
        saved = json.loads(path.read_text())
        assert saved["language"] == "de"
        assert saved["title"] == "Title in de"

    def test_creates_directories(self, tmp_path: Path):
        _save_translation(tmp_path, 99, "fr", _fake_translation(99, "fr"))
        assert (tmp_path / "99" / "translations" / "fr.json").exists()

    def test_overwrites_existing(self, tmp_path: Path):
        _save_translation(tmp_path, 42, "de", {"title": "Old"})
        _save_translation(tmp_path, 42, "de", {"title": "New"})
        data = json.loads((tmp_path / "42" / "translations" / "de.json").read_text())
        assert data["title"] == "New"


# --- _fetch_translation ---


class TestFetchTranslation:
    def test_returns_data_on_success(self):
        translation = _fake_translation(42, "de")
        api = FakeTranslationAPI({(42, "de"): translation})
        result = _fetch_translation(api, shop_id=1, listing_id=42, language="de")
        assert result == translation

    def test_returns_none_on_404(self):
        api = FakeTranslationAPI({})
        result = _fetch_translation(api, shop_id=1, listing_id=42, language="de")
        assert result is None

    def test_raises_non_404_errors(self):
        class ErrorAPI:
            def get_listing_translation(self, **kwargs):
                raise Exception("500 Internal Server Error")

        with pytest.raises(Exception, match="500"):
            _fetch_translation(ErrorAPI(), shop_id=1, listing_id=42, language="de")


# --- pull_translations_for_listings ---


class TestPullTranslationsForListings:
    def test_pulls_and_saves(self, tmp_path: Path):
        translations = {
            (42, "de"): _fake_translation(42, "de"),
            (42, "fr"): _fake_translation(42, "fr"),
            (99, "de"): _fake_translation(99, "de"),
        }
        api = FakeTranslationAPI(translations)
        count = pull_translations_for_listings(
            api, shop_id=1, listings_dir=tmp_path, listing_ids=[42, 99], languages=["de", "fr"]
        )
        assert count == 3
        assert (tmp_path / "42" / "translations" / "de.json").exists()
        assert (tmp_path / "42" / "translations" / "fr.json").exists()
        assert (tmp_path / "99" / "translations" / "de.json").exists()
        assert not (tmp_path / "99" / "translations" / "fr.json").exists()

    def test_skips_404(self, tmp_path: Path):
        api = FakeTranslationAPI({})
        count = pull_translations_for_listings(
            api, shop_id=1, listings_dir=tmp_path, listing_ids=[42], languages=["de"]
        )
        assert count == 0
        assert not (tmp_path / "42" / "translations").exists()

    def test_single_listing(self, tmp_path: Path):
        translations = {(42, "de"): _fake_translation(42, "de")}
        api = FakeTranslationAPI(translations)
        count = pull_translations_for_listings(
            api, shop_id=1, listings_dir=tmp_path, listing_ids=[42], languages=["de"]
        )
        assert count == 1
        assert api.calls == [(42, "de")]

    def test_no_listings(self, tmp_path: Path):
        api = FakeTranslationAPI({})
        count = pull_translations_for_listings(api, shop_id=1, listings_dir=tmp_path, listing_ids=[], languages=["de"])
        assert count == 0


# --- _load_local_translation ---


class TestLoadLocalTranslation:
    def test_loads_existing(self, tmp_path: Path):
        _save_translation(tmp_path, 42, "de", _fake_translation(42, "de"))
        result = _load_local_translation(tmp_path, 42, "de")
        assert result is not None
        assert result["language"] == "de"

    def test_returns_none_for_missing(self, tmp_path: Path):
        assert _load_local_translation(tmp_path, 42, "de") is None


# --- _diff_translation ---


class TestDiffTranslation:
    def test_no_changes(self):
        local = {"title": "Titel", "description": "Beschreibung", "tags": ["tag1"]}
        remote = {"title": "Titel", "description": "Beschreibung", "tags": ["tag1"]}
        assert _diff_translation(local, remote) == {}

    def test_title_changed(self):
        local = {"title": "Neuer Titel", "description": "Same"}
        remote = {"title": "Alter Titel", "description": "Same"}
        diff = _diff_translation(local, remote)
        assert diff == {"title": "Neuer Titel"}

    def test_multiple_changes(self):
        local = {"title": "New", "description": "New desc", "tags": ["new"]}
        remote = {"title": "Old", "description": "Old desc", "tags": ["old"]}
        diff = _diff_translation(local, remote)
        assert set(diff.keys()) == {"title", "description", "tags"}

    def test_remote_none_all_fields_new(self):
        local = {"title": "Titel", "description": "Desc", "tags": ["t"]}
        diff = _diff_translation(local, None)
        assert diff == {"title": "Titel", "description": "Desc", "tags": ["t"]}

    def test_ignores_non_translation_fields(self):
        local = {"title": "Same", "listing_id": 42, "language": "de"}
        remote = {"title": "Same", "listing_id": 42, "language": "de"}
        assert _diff_translation(local, remote) == {}

    def test_field_missing_in_local_skipped(self):
        local = {"title": "Same"}
        remote = {"title": "Same", "description": "Remote only"}
        assert _diff_translation(local, remote) == {}


# --- _scan_local_translations ---


class TestScanLocalTranslations:
    def test_finds_existing_files(self, tmp_path: Path):
        _save_translation(tmp_path, 42, "de", _fake_translation(42, "de"))
        _save_translation(tmp_path, 42, "fr", _fake_translation(42, "fr"))
        pairs = _scan_local_translations(tmp_path, [42], ["de", "fr", "es"])
        assert pairs == [(42, "de"), (42, "fr")]

    def test_no_files(self, tmp_path: Path):
        pairs = _scan_local_translations(tmp_path, [42], ["de"])
        assert pairs == []

    def test_multiple_listings(self, tmp_path: Path):
        _save_translation(tmp_path, 42, "de", _fake_translation(42, "de"))
        _save_translation(tmp_path, 99, "de", _fake_translation(99, "de"))
        pairs = _scan_local_translations(tmp_path, [42, 99], ["de"])
        assert pairs == [(42, "de"), (99, "de")]
