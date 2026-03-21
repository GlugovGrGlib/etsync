import json
from datetime import datetime, timezone
from pathlib import Path

import typer

from etsync.auth import refresh_save
from etsync.config import get_data_dir, settings

LIMIT = 100


def _get_api():  # noqa: ANN202
    """Build an authenticated EtsyAPI client."""
    from etsyv3 import EtsyAPI

    try:
        token = settings.access_token
        refresh_token = settings.refresh_token
        expires_at = settings.expires_at
    except AttributeError:
        typer.echo("No authentication tokens found. Run `etsync login` first.", err=True)
        raise typer.Exit(1)

    expiry = datetime.utcfromtimestamp(expires_at)  # etsyv3 requires naive UTC
    api = EtsyAPI(
        keystring=settings.api_keystring,
        token=token,
        refresh_token=refresh_token,
        expiry=expiry,
        refresh_save=refresh_save,
    )
    # Etsy v3 requires keystring:shared_secret in x-api-key for data endpoints,
    # but refresh uses keystring alone as client_id — so override only the header.
    api.session.headers["x-api-key"] = f"{settings.api_keystring}:{settings.shared_secret}"
    return api


def _fetch_all_listings(api, shop_id: int) -> list[dict]:  # noqa: ANN001
    """Fetch all active listings, handling pagination."""
    listings: list[dict] = []
    offset = 0
    while True:
        resp = api.get_listings_by_shop(shop_id, limit=LIMIT, offset=offset)
        results = resp.get("results", [])
        listings.extend(results)
        count = resp.get("count", 0)
        if offset + LIMIT >= count:
            break
        offset += LIMIT
    return listings


def _save_listing(listings_dir: Path, listing: dict) -> None:
    listing_id = listing["listing_id"]
    path = listings_dir / f"{listing_id}.json"
    path.write_text(json.dumps(listing, indent=2, ensure_ascii=False) + "\n")


def _build_index_entry(listing: dict) -> dict:
    """Build a single index entry with enhanced metadata."""
    listing_id = listing["listing_id"]
    price_data = listing.get("price", {})
    return {
        "listing_id": listing_id,
        "title": listing.get("title", ""),
        "state": listing.get("state", ""),
        "updated_timestamp": listing.get("last_modified_timestamp", 0),
        "url": f"https://www.etsy.com/listing/{listing_id}",
        "creation_timestamp": listing.get("creation_timestamp", 0),
        "price": {
            "amount": price_data.get("amount", 0),
            "currency": price_data.get("currency_code", ""),
        },
        "tags": listing.get("tags", []),
        "quantity": listing.get("quantity", 0),
    }


def _save_index(listings_dir: Path, listings: list[dict], synced_at: str) -> None:
    entries = [_build_index_entry(listing) for listing in listings]
    index = {
        "synced_at": synced_at,
        "count": len(entries),
        "listings": entries,
    }
    (listings_dir / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")


def pull_listings() -> None:
    """Download all active shop listings as JSON files."""
    from etsync.data_repo import commit_sync

    api = _get_api()
    try:
        shop_id = int(settings.shop_id)
    except AttributeError:
        typer.echo("No shop_id configured. Set it in settings.toml or .secrets.toml.", err=True)
        raise typer.Exit(1)
    data_dir = get_data_dir()
    listings_dir = data_dir / "listings"
    listings_dir.mkdir(parents=True, exist_ok=True)

    synced_at = datetime.now(timezone.utc).isoformat()

    typer.echo(f"Pulling listings for shop {shop_id}...")
    listings = _fetch_all_listings(api, shop_id)

    if not listings:
        typer.echo("No active listings found.")
        _save_index(listings_dir, [], synced_at)
        commit_sync(data_dir, count=0, synced_at=synced_at)
        return

    for listing in listings:
        _save_listing(listings_dir, listing)

    _save_index(listings_dir, listings, synced_at)
    commit_sync(data_dir, count=len(listings), synced_at=synced_at)
    typer.echo(f"Saved {len(listings)} listing(s) to {listings_dir}")
