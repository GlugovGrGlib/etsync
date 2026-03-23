"""Push local listing changes to the Etsy API, sending only modified fields."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import typer

from etsync.config import get_data_dir, settings

ETSY_API_BASEURL = "https://api.etsy.com/v3/application"

# Fields the Etsy API accepts for update via PATCH.
UPDATABLE_FIELDS: set[str] = {
    "title",
    "description",
    "materials",
    "tags",
    "taxonomy_id",
    "should_auto_renew",
    "shipping_profile_id",
    "shop_section_id",
    "item_weight",
    "item_length",
    "item_width",
    "item_height",
    "item_weight_unit",
    "item_dimensions_unit",
    "is_taxable",
    "who_made",
    "when_made",
    "featured_rank",
    "is_personalizable",
    "personalization_is_required",
    "personalization_char_count_max",
    "personalization_instructions",
    "state",
    "is_supply",
    "production_partner_ids",
    "listing_type",
}


@dataclass
class FieldChange:
    field: str
    old_value: Any
    new_value: Any


@dataclass
class ListingDiff:
    listing_id: int
    title: str
    changes: list[FieldChange] = field(default_factory=list)


def _normalize_value(value: Any) -> Any:
    """Normalize values for comparison (sort lists, coerce types)."""
    if isinstance(value, list):
        return sorted(str(v) for v in value)
    return value


def diff_listing(local: dict, remote: dict) -> ListingDiff:
    """Compare local listing against remote, returning only changed updatable fields."""
    listing_id = local["listing_id"]
    title = local.get("title", remote.get("title", ""))
    changes: list[FieldChange] = []

    for f in UPDATABLE_FIELDS:
        if f not in local:
            continue
        local_val = local[f]
        remote_val = remote.get(f)
        if _normalize_value(local_val) != _normalize_value(remote_val):
            changes.append(FieldChange(field=f, old_value=remote_val, new_value=local_val))

    return ListingDiff(listing_id=listing_id, title=title, changes=changes)


def _format_diff(diff: ListingDiff) -> str:
    """Format a listing diff for display."""
    lines = [f'Listing {diff.listing_id}: "{diff.title}"']
    for change in diff.changes:
        old = _truncate(change.old_value)
        new = _truncate(change.new_value)
        lines.append(f"  {change.field}: {old} -> {new}")
    return "\n".join(lines)


def _truncate(value: Any, max_len: int = 80) -> str:
    """Truncate long values for display."""
    s = repr(value)
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def _load_local_listings(listings_dir: Path, listing_id: int | None = None) -> list[dict]:
    """Load local listing JSON files. Supports both nested and flat layout."""
    results = []
    if listing_id is not None:
        # Try nested first, then flat
        nested = listings_dir / str(listing_id) / "listing.json"
        flat = listings_dir / f"{listing_id}.json"
        path = nested if nested.exists() else flat
        if not path.exists():
            typer.echo(f"Local listing file not found for {listing_id}", err=True)
            raise typer.Exit(1)
        results.append(json.loads(path.read_text()))
        return results

    # Load all listings from nested dirs and flat files
    seen: set[int] = set()
    for child in sorted(listings_dir.iterdir()):
        if child.is_dir() and child.name.isdigit():
            listing_path = child / "listing.json"
            if listing_path.exists():
                data = json.loads(listing_path.read_text())
                lid = data.get("listing_id")
                if lid and lid not in seen:
                    results.append(data)
                    seen.add(lid)
        elif child.suffix == ".json" and child.stem.isdigit() and child.name != "index.json":
            data = json.loads(child.read_text())
            lid = data.get("listing_id")
            if lid and lid not in seen:
                results.append(data)
                seen.add(lid)
    return results


ETSY_TAG_MAX_LENGTH = 20
ETSY_TITLE_MAX_LENGTH = 140
ETSY_MAX_TAGS = 13


@dataclass
class ValidationError:
    field: str
    message: str


def validate_listing(listing: dict) -> list[ValidationError]:
    """Validate listing fields against Etsy API constraints."""
    errors: list[ValidationError] = []

    title = listing.get("title")
    if isinstance(title, str) and len(title) > ETSY_TITLE_MAX_LENGTH:
        errors.append(ValidationError("title", f"exceeds {ETSY_TITLE_MAX_LENGTH} chars ({len(title)})"))

    tags = listing.get("tags")
    if isinstance(tags, list):
        if len(tags) > ETSY_MAX_TAGS:
            errors.append(ValidationError("tags", f"more than {ETSY_MAX_TAGS} tags ({len(tags)})"))
        for tag in tags:
            if len(tag) > ETSY_TAG_MAX_LENGTH:
                errors.append(ValidationError("tags", f"'{tag}' exceeds {ETSY_TAG_MAX_LENGTH} chars ({len(tag)})"))

    return errors


def _extract_error_detail(exc: Exception) -> str:
    """Extract the response body from an HTTP error, falling back to str(exc)."""
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            return f"{response.status_code} {response.reason}: {response.text}"
        except Exception:
            pass
    return str(exc)


def _push_listing(api, shop_id: int, listing_id: int, changes: list[FieldChange]) -> None:  # noqa: ANN001
    """Push changed fields to the Etsy API using PATCH."""
    from etsyv3.models.listing_request import UpdateListingRequest

    kwargs: dict[str, Any] = {}
    for change in changes:
        kwargs[change.field] = change.new_value

    request = UpdateListingRequest(**kwargs)
    api.update_listing(shop_id=shop_id, listing_id=listing_id, listing=request)


def push_listings(
    listing_id: Optional[int] = typer.Option(None, "--id", help="Push a single listing"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show diff without applying changes"),
) -> None:
    """Push local listing changes to Etsy, sending only modified fields."""
    from etsync.listings.pull import _get_api

    api = _get_api()
    try:
        shop_id = int(settings.shop_id)
    except AttributeError:
        typer.echo("No shop_id configured.", err=True)
        raise typer.Exit(1)

    data_dir = get_data_dir()
    listings_dir = data_dir / "listings"
    if not listings_dir.exists():
        typer.echo("No listings directory found. Run `etsync pull listings` first.", err=True)
        raise typer.Exit(1)

    local_listings = _load_local_listings(listings_dir, listing_id)
    if not local_listings:
        typer.echo("No local listing files found.")
        return

    updated_items: list[tuple[int, str, int]] = []  # (id, title, field_count)
    skipped_items: list[tuple[int, str, str]] = []  # (id, title, reason)
    failed_items: list[tuple[int, str, str]] = []  # (id, title, error)

    for local in local_listings:
        lid = local["listing_id"]
        title = local.get("title", "")
        try:
            remote = api.get_listing(listing_id=lid)
        except Exception as exc:
            error_detail = _extract_error_detail(exc)
            typer.echo(f"  [{lid}] Failed to fetch remote: {error_detail}", err=True)
            failed_items.append((lid, title, f"fetch error: {error_detail}"))
            continue

        diff = diff_listing(local, remote)
        if not diff.changes:
            skipped_items.append((lid, diff.title, "no changes"))
            continue

        typer.echo(_format_diff(diff))

        # Validate changed fields before pushing
        changed_data = {c.field: c.new_value for c in diff.changes}
        errors = validate_listing(changed_data)
        if errors:
            for err in errors:
                typer.echo(f"  [{lid}] INVALID {err.field}: {err.message}", err=True)
            failed_items.append((lid, diff.title, "; ".join(f"{e.field}: {e.message}" for e in errors)))
            continue

        if dry_run:
            skipped_items.append((lid, diff.title, "dry run"))
            continue

        try:
            _push_listing(api, shop_id, lid, diff.changes)
            typer.echo(f"  [{lid}] Updated ({len(diff.changes)} field(s))")
            updated_items.append((lid, diff.title, len(diff.changes)))
        except Exception as exc:
            error_detail = _extract_error_detail(exc)
            typer.echo(f"  [{lid}] Failed: {error_detail}", err=True)
            failed_items.append((lid, diff.title, error_detail))

    _print_summary(updated_items, skipped_items, failed_items)


def _print_summary(
    updated: list[tuple[int, str, int]],
    skipped: list[tuple[int, str, str]],
    failed: list[tuple[int, str, str]],
) -> None:
    """Print a detailed push summary grouped by outcome."""
    typer.echo(f"\nSummary: {len(updated)} updated, {len(skipped)} skipped, {len(failed)} failed")

    if updated:
        typer.echo("\nUpdated:")
        for lid, title, count in updated:
            typer.echo(f"  [{lid}] {title} ({count} field(s))")

    if failed:
        typer.echo("\nFailed:")
        for lid, title, reason in failed:
            typer.echo(f"  [{lid}] {title} — {reason}")

    if skipped:
        typer.echo("\nSkipped:")
        for lid, title, reason in skipped:
            typer.echo(f"  [{lid}] {title} — {reason}")
