# Design: Listings Push

## Technical Approach

The push command mirrors the pull pipeline in reverse. It reads local TOML files, fetches the corresponding live listing from the API, diffs them field-by-field, presents the changes, and — after confirmation — sends only the modified fields to the Etsy API.

## Architecture Decisions

### Diff engine: field-level comparison

**Rationale**: Etsy's `update_listing()` accepts partial payloads — only send what changed. A field-level diff avoids sending unchanged data (which could trigger unnecessary validation or overwrite concurrent edits) and produces a clear, human-readable change report.

Implementation:
- Load local listing from `{data_dir}/listings/{listing_id}.toml`
- Fetch live listing via `EtsyAPI.get_listing(listing_id)`
- Define `UPDATABLE_FIELDS` — the subset of listing fields that the Etsy API accepts for update (e.g., `title`, `description`, `price`, `quantity`, `tags`, `materials`, `who_made`, `when_made`, `taxonomy_id`, `is_personalizable`, `shipping_profile_id`, `state`)
- Define `SKIP_FIELDS` — read-only fields excluded from comparison (`listing_id`, `shop_id`, `user_id`, `creation_tsz`, `ending_tsz`, `original_creation_tsz`, `last_modified_tsz`, `state_tsz`, `url`, `views`, `num_favorers`)
- For each field in `UPDATABLE_FIELDS`: compare `local[field]` vs `remote[field]`. Collect differences into a `ListingDiff` dataclass

```python
@dataclass
class FieldChange:
    field: str
    old_value: Any
    new_value: Any

@dataclass
class ListingDiff:
    listing_id: int
    title: str  # for display
    changes: list[FieldChange]
    has_conflict: bool  # True if remote changed since last pull
    remote_modified_tsz: float
    local_pull_tsz: float  # from index.toml or file mtime
```

### Color-coded terminal output

**Rationale**: Quick visual scanning of changes. Typer wraps `rich` for styled output.

Format per listing:
```
Listing 1234567890: "Vintage Ceramic Mug"
  title:       "Vintage Ceramic Mug" -> "Handmade Vintage Ceramic Mug"
  description: [changed, 12 chars added]
  price:       19.99 -> 24.99
  tags:        ["vintage", "mug"] -> ["vintage", "mug", "ceramic"]
```

- Field names in white
- Old values in red
- New values in green
- Long text fields (description) show a summary rather than full content; `--verbose` shows full text

### Confirmation flow

Three modes after displaying the diff:

1. **Apply all** (`y`) — push every changed listing
2. **Reject all** (`n`) — abort, no changes made
3. **Listing-by-listing** (`l`) — prompt per listing: apply (y), skip (s), or abort remaining (n)

In `--dry-run` mode, the diff is printed and the command exits with code 0 (changes found) or code 1 (no changes). No confirmation prompt.

### Conflict detection

**Rationale**: Prevent overwriting changes made on Etsy (via web UI or another tool) since the last pull.

Strategy:
- During `pull`, record `last_modified_tsz` for each listing in `index.toml` under a `pull_metadata` section
- During `push`, compare the stored `last_modified_tsz` against the freshly-fetched value
- If they differ, mark the listing as conflicted
- Conflicted listings show a warning: `CONFLICT: listing was modified on Etsy since last pull (remote: 2026-03-20T14:30:00, pulled: 2026-03-19T10:00:00)`
- By default, conflicted listings are skipped. Use `--force` to push anyway

### Backup before push

**Rationale**: Safety net. If a push goes wrong, the user can inspect or restore the pre-push remote state.

- Before pushing, save the current remote state of each changed listing to `{data_dir}/listings/.backups/{listing_id}_{timestamp}.toml`
- Backups are never auto-deleted; user can clean up manually

### Push implementation

Use `etsyv3.EtsyAPI.update_listing(listing_id, **changed_fields)`:
- Only send fields present in the diff
- Handle API errors per listing (400 validation, 403 auth, 404 not found, 429 rate limit)
- On rate limit (429), wait and retry with exponential backoff (max 3 retries)
- Report results as each listing completes: success or failure with error details
- At the end, print a summary: `N updated, M skipped, K failed`

### CLI interface

```
etsync push listings              # push all changed listings
etsync push listings --id 12345   # push a single listing
etsync push listings --dry-run    # show diff without applying
etsync push listings --force      # push even if conflicts detected
etsync push listings --verbose    # show full field values in diff
```

`push` is a new Typer group (like `pull`), registered in `cli.py`. The `listings` subcommand is registered by `etsync/listings/push.py`.

## Data Flow

```
etsync push listings
  |
  +- config.py: load settings (shop_id, data_dir, tokens)
  +- auth check: verify tokens exist, fail early if not
  +- EtsyAPI(keystring, token, refresh_token, expiry, refresh_save=...)
  |
  +- Load local listing files from {data_dir}/listings/*.toml
  |    +- If --id given, load only that listing
  |    +- Parse index.toml for pull_metadata (last_modified_tsz per listing)
  |
  +- For each local listing:
  |    +- Fetch live listing via EtsyAPI.get_listing(listing_id)
  |    +- Compare UPDATABLE_FIELDS: local vs remote
  |    +- Check conflict: remote.last_modified_tsz vs index.pull_metadata
  |    +- Collect into ListingDiff
  |
  +- Filter: only listings with changes (and optionally conflicts)
  |
  +- Display diff summary (color-coded)
  |    +- If --dry-run: print and exit
  |
  +- Prompt for confirmation (y/n/l)
  |
  +- For each confirmed listing:
  |    +- Backup remote state to .backups/
  |    +- EtsyAPI.update_listing(listing_id, **changed_fields)
  |    +- Report success/failure
  |
  +- Print summary: N updated, M skipped, K failed
  +- If any updated: refresh index.toml with new last_modified_tsz
```

## File Changes

| Action | Path | Description |
|--------|------|-------------|
| Create | `etsync/listings/push.py` | Push implementation: diff, confirm, update |
| Create | `etsync/listings/diff.py` | Diff engine: field comparison, ListingDiff dataclass |
| Create | `etsync/listings/backup.py` | Backup remote state before push |
| Create | `etsync/listings/display.py` | Color-coded diff display, confirmation prompts |
| Create | `tests/test_push.py` | Push command tests (mocked API) |
| Create | `tests/test_diff.py` | Diff engine unit tests |
| Modify | `etsync/cli.py` | Add `push` Typer group, register `listings` subcommand |
| Modify | `etsync/listings/__init__.py` | Export push-related symbols |
| Modify | `etsync/listings/pull.py` | Record `last_modified_tsz` in index.toml `pull_metadata` section |

## Error Handling

| Error | Behavior |
|-------|----------|
| No local listing files found | Print message, exit cleanly |
| Listing ID not found locally (`--id`) | Print error with available IDs, exit code 1 |
| Listing deleted on Etsy (404) | Report as failed, continue with remaining |
| Authentication expired (401/403) | Print message to re-run `etsync login`, exit code 1 |
| Validation error from API (400) | Report field-level errors, continue with remaining |
| Rate limit (429) | Retry with exponential backoff, max 3 attempts |
| Network error | Report, continue with remaining listings |
| All listings failed | Exit code 1 |
| Partial success | Exit code 0, print summary with failures noted |
