"""Pull and push listing translations via the Etsy API."""

import json
from pathlib import Path
from typing import Optional

import typer

from etsync.config import get_data_dir, settings


def _load_listing_ids(listings_dir: Path) -> list[int]:
    """Load listing IDs from index.json."""
    index_path = listings_dir / "index.json"
    if not index_path.exists():
        typer.echo("No listings index found. Run `etsync pull listings` first.", err=True)
        raise typer.Exit(1)
    index = json.loads(index_path.read_text())
    return [entry["listing_id"] for entry in index.get("listings", [])]


def _fetch_translation(api, shop_id: int, listing_id: int, language: str) -> dict | None:  # noqa: ANN001
    """Fetch a single translation, returning None on 404."""
    try:
        return api.get_listing_translation(
            shop_id=shop_id,
            listing_id=listing_id,
            language=language,
        )
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


def _save_translation(listings_dir: Path, listing_id: int, language: str, data: dict) -> None:
    """Save a translation to {listing_id}/translations/{language}.json."""
    translations_dir = listings_dir / str(listing_id) / "translations"
    translations_dir.mkdir(parents=True, exist_ok=True)
    path = translations_dir / f"{language}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def pull_translations_for_listings(
    api,  # noqa: ANN001
    shop_id: int,
    listings_dir: Path,
    listing_ids: list[int],
    languages: list[str],
) -> int:
    """Pull translations for given listings and languages. Returns count of saved translations."""
    count = 0
    for listing_id in listing_ids:
        for language in languages:
            data = _fetch_translation(api, shop_id, listing_id, language)
            if data is not None:
                _save_translation(listings_dir, listing_id, language, data)
                count += 1
    typer.echo(f"Pulled {count} translation(s) for {len(listing_ids)} listing(s).")
    return count


def pull_translations(
    listing_id: Optional[int] = typer.Option(None, "--id", help="Pull translations for a single listing"),
) -> None:
    """Pull translations for all listings (or a single one with --id)."""
    from etsync.listings.pull import _get_api

    languages: list[str] = settings.languages
    if not languages:
        typer.echo("No languages configured in settings.toml", err=True)
        raise typer.Exit(1)

    api = _get_api()
    shop_id = int(settings.shop_id)
    data_dir = get_data_dir()
    listings_dir = data_dir / "listings"

    if listing_id is not None:
        listing_ids = [listing_id]
    else:
        listing_ids = _load_listing_ids(listings_dir)

    pull_translations_for_listings(api, shop_id, listings_dir, listing_ids, languages)


# --- Push translations ---

ETSY_API_BASEURL = "https://api.etsy.com/v3/application"

# Fields that can be set on a translation.
TRANSLATION_FIELDS: set[str] = {"title", "description", "tags"}


def _load_local_translation(listings_dir: Path, listing_id: int, language: str) -> dict | None:
    """Load a local translation file, returning None if it doesn't exist."""
    path = listings_dir / str(listing_id) / "translations" / f"{language}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def _diff_translation(local: dict, remote: dict | None) -> dict:
    """Return only the fields that differ between local and remote.

    If remote is None (no translation exists yet), all local fields are new.
    """
    changed: dict = {}
    for field in TRANSLATION_FIELDS:
        if field not in local:
            continue
        local_val = local[field]
        remote_val = remote.get(field) if remote else None
        if local_val != remote_val:
            changed[field] = local_val
    return changed


def _create_translation(api, shop_id: int, listing_id: int, language: str, payload: dict) -> None:  # noqa: ANN001
    """POST a new translation via the Etsy REST API."""
    url = f"{ETSY_API_BASEURL}/shops/{shop_id}/listings/{listing_id}/translations/{language}"
    resp = api.session.post(url, json=payload)
    _check_response(resp)


def _update_translation(api, shop_id: int, listing_id: int, language: str, payload: dict) -> None:  # noqa: ANN001
    """PUT an updated translation via the Etsy REST API."""
    url = f"{ETSY_API_BASEURL}/shops/{shop_id}/listings/{listing_id}/translations/{language}"
    resp = api.session.put(url, json=payload)
    _check_response(resp)


def _check_response(resp) -> None:  # noqa: ANN001
    """Raise with the response body included in the error message."""
    if not resp.ok:
        raise Exception(f"{resp.status_code} {resp.reason}: {resp.text}")


def _scan_local_translations(listings_dir: Path, listing_ids: list[int], languages: list[str]) -> list[tuple[int, str]]:
    """Return (listing_id, language) pairs that have local translation files."""
    pairs: list[tuple[int, str]] = []
    for lid in listing_ids:
        for lang in languages:
            path = listings_dir / str(lid) / "translations" / f"{lang}.json"
            if path.exists():
                pairs.append((lid, lang))
    return pairs


def push_translations(
    listing_id: Optional[int] = typer.Option(None, "--id", help="Push translations for a single listing"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show diff without applying changes"),
) -> None:
    """Push local translation changes to Etsy, sending only modified fields."""
    from etsync.listings.pull import _get_api

    languages: list[str] = settings.languages
    if not languages:
        typer.echo("No languages configured in settings.toml", err=True)
        raise typer.Exit(1)

    api = _get_api()
    shop_id = int(settings.shop_id)
    data_dir = get_data_dir()
    listings_dir = data_dir / "listings"

    if listing_id is not None:
        listing_ids = [listing_id]
    else:
        listing_ids = _load_listing_ids(listings_dir)

    pairs = _scan_local_translations(listings_dir, listing_ids, languages)
    if not pairs:
        typer.echo("No local translation files found.")
        return

    created = 0
    updated = 0
    skipped = 0
    failed = 0

    for lid, lang in pairs:
        local = _load_local_translation(listings_dir, lid, lang)
        if local is None:
            skipped += 1
            continue

        try:
            remote = _fetch_translation(api, shop_id, lid, lang)
        except Exception as exc:
            from etsync.listings.push import _extract_error_detail

            typer.echo(f"  [{lid}/{lang}] Failed to fetch remote: {_extract_error_detail(exc)}", err=True)
            failed += 1
            continue

        diff = _diff_translation(local, remote)
        if not diff:
            skipped += 1
            continue

        action = "create" if remote is None else "update"
        typer.echo(f"  [{lid}/{lang}] {action}: {', '.join(diff.keys())}")

        # Validate translation fields before pushing
        from etsync.listings.push import validate_listing

        errors = validate_listing(diff)
        if errors:
            for err in errors:
                typer.echo(f"  [{lid}/{lang}] INVALID {err.field}: {err.message}", err=True)
            failed += 1
            continue

        if dry_run:
            skipped += 1
            continue

        # Etsy PUT/POST requires all translation fields, not just changed ones.
        payload = {f: local[f] for f in TRANSLATION_FIELDS if f in local}

        try:
            if remote is None:
                _create_translation(api, shop_id, lid, lang, payload)
                created += 1
            else:
                _update_translation(api, shop_id, lid, lang, payload)
                updated += 1
        except Exception as exc:
            typer.echo(f"  [{lid}/{lang}] Failed: {exc}", err=True)
            failed += 1

    typer.echo(f"\nSummary: {created} created, {updated} updated, {skipped} skipped, {failed} failed")
