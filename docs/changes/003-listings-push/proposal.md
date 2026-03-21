# Proposal: Listings Push (Round-Trip Editing)

## Intent

Enable round-trip editing of Etsy listings. Users can pull listings to local TOML files, edit them with any text editor or script, then push changes back to Etsy. This closes the loop on the core workflow: pull, edit, review diff, push.

Currently `etsync pull listings` downloads data but there is no way to send modifications back. Shop owners must still use the Etsy web UI for edits, defeating the purpose of a scriptable CLI.

## Scope

### In scope

- `etsync push listings` command — compares local TOML state against live Etsy state, shows a human-readable diff, requires user confirmation, then applies changes via the API
- Field-level diffing between local files and freshly-fetched API data
- Color-coded diff output in the terminal
- Confirmation flow (approve all, reject all, or listing-by-listing)
- Single-listing push (`--id <listing_id>`)
- Dry-run mode (`--dry-run`) that shows what would change without applying
- Conflict detection — warn if a listing was modified on Etsy since the last pull
- Backup of current remote state before applying changes
- Partial failure handling — report per-listing success/failure

### Out of scope

- Creating new listings (only updating existing ones)
- Deleting listings
- Image/file uploads
- Inventory quantity updates (separate domain)
- Shipping profile changes
- Bulk field transforms or templating

## Approach

1. **Fetch current state** — For each local listing file, fetch the corresponding listing from the Etsy API to get the live state.

2. **Diff engine** — Compare each TOML field against the API response field-by-field. Only fields that differ are flagged. Non-updatable fields (e.g., `listing_id`, `shop_id`, `creation_tsz`) are excluded from comparison.

3. **Present changes** — Display a summary: how many listings changed, which fields per listing, old vs new values. Color-coded terminal output (red for removals, green for additions).

4. **Confirm** — Prompt the user: apply all (y), reject all (n), or review listing-by-listing (l). In `--dry-run` mode, skip confirmation and just print the diff.

5. **Push** — Call `etsyv3.EtsyAPI.update_listing()` for each confirmed listing, sending only the changed fields. Log success/failure per listing.

6. **Safety** — Before pushing, save the current remote state as a backup TOML file. Detect conflicts by comparing the last-pulled timestamp against the listing's `last_modified_tsz` from the API.

## Future

These will become separate OpenSpec changes:

- **Listings create** — create new listings from local TOML templates
- **Listings delete** — remove listings via CLI
- **Batch push** — push across multiple domains (listings + inventory + shipping) in one command
- **Auto-merge conflicts** — three-way merge when both local and remote have changed
