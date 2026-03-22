# Design: Listing Translations Management

## Technical Approach

Translations are a sub-resource of listings. We add a `translations` module under `etsync/listings/` that handles pull and push. The `etsyv3` library supports `get_listing_translation` but lacks create/update — we implement those directly via the existing authenticated session.

```
etsync/listings/
  __init__.py          # existing — register new commands
  pull.py              # existing — add --with-translations flag
  translations.py      # NEW — pull/push translation logic
```

## Architecture Decisions

### Translations as subdirectories per listing

**Rationale**: Currently listings are flat files (`{listing_id}.json`). Translations belong to a listing, so we nest them:

```
listings/
  index.json
  1234567890/
    listing.json
    translations/
      de.json
      fr.json
  9876543210/
    listing.json
    translations/
      de.json
```

This groups related data and scales cleanly with more languages. The migration from flat to nested happens automatically on the next `pull listings`.

### Direct API calls for create/update translations

**Rationale**: The `etsyv3` library's `create_listing_translation` and `update_listing_translation` raise `NotImplementedError`. Rather than forking or monkeypatching the library, we use the already-authenticated `api.session` to call the Etsy REST endpoints directly. The endpoints are:

- `GET /v3/application/shops/{shop_id}/listings/{listing_id}/translations/{language}` — already works via `etsyv3`
- `POST /v3/application/shops/{shop_id}/listings/{listing_id}/translations/{language}` — create
- `PUT /v3/application/shops/{shop_id}/listings/{listing_id}/translations/{language}` — update

Request body for create/update:
```json
{
  "title": "Translated title",
  "description": "Translated description",
  "tags": ["tag1", "tag2"]
}
```

All three fields are optional — you can push just a title without touching description/tags.

### Languages configured in settings.toml

**Rationale**: Each shop targets different markets. A `languages` list in `settings.toml` keeps this per-environment:

```toml
[default]
languages = ["de", "fr"]

[glugowskimetalartist]
languages = ["de", "fr", "nl"]
```

Etsy uses IETF language tags: `de`, `fr`, `nl`, `it`, `es`, `pt`, `ja`, `pl`, etc.

### 404 handling on pull

**Rationale**: Not every listing has translations for every configured language. The API returns 404 for missing translations. We catch this and skip — no error, no empty file. This way local files only exist for translations that are actually set on Etsy.

## Data Flow

### Pull translations

```
etsync pull translations [--id LISTING_ID]
  │
  ├─ Load index.json → get all listing IDs (or use --id)
  ├─ Load languages from settings.toml
  │
  ├─ For each listing × language:
  │    ├─ GET /shops/{shop_id}/listings/{listing_id}/translations/{language}
  │    ├─ 404 → skip (no translation exists)
  │    └─ 200 → save to {listing_id}/translations/{language}.json
  │
  └─ Log summary: "Pulled N translations for M listings"
```

### Push translations

```
etsync push translations [--id LISTING_ID] [--dry-run]
  │
  ├─ Scan local translation files
  ├─ For each {listing_id}/translations/{language}.json:
  │    ├─ Read local file
  │    ├─ GET remote translation (to determine create vs update)
  │    ├─ Compare local vs remote
  │    ├─ If unchanged → skip
  │    ├─ If --dry-run → print diff, skip
  │    ├─ If no remote → POST (create)
  │    └─ If remote exists → PUT (update)
  │
  └─ Log summary: "Pushed N translations (C created, U updated, S skipped)"
```

### Validation before push

**Rationale**: Etsy enforces constraints that cause opaque API errors. We validate locally before sending to give clear, actionable feedback.

Constraints enforced:
- **Tags**: each tag ≤ 20 characters, max 13 tags per listing
- **Title**: ≤ 140 characters

Validation runs on both listing push and translation push. Invalid listings are skipped with a clear error message showing which field and value failed.

## File Changes

| Action | Path | Description |
|--------|------|-------------|
| Create | `etsync/listings/translations.py` | Pull/push translation logic + direct API calls |
| Create | `etsync/listings/push.py` | Push listings with diff-only updates + validation |
| Modify | `etsync/listings/__init__.py` | Register `translations` subcommands under `pull` and `push` |
| Modify | `etsync/listings/pull.py` | Add `--with-translations` flag, migrate to nested directory layout |
| Modify | `etsync/cli.py` | Add `push` Typer group |
| Modify | `etsync/config.py` | Add `languages` setting with default `[]` |
| Modify | `settings.toml` | Add `languages` example |
| Create | `tests/test_translations.py` | Tests for pull/push translations |
| Create | `tests/test_push.py` | Tests for push listings, diff engine, validation |
