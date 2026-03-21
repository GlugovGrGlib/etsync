# Tasks: Listings Push

## 1. Diff Engine

- [ ] 1.1 Define `UPDATABLE_FIELDS` and `SKIP_FIELDS` constants in `etsync/listings/diff.py`
- [ ] 1.2 Create `FieldChange` and `ListingDiff` dataclasses
- [ ] 1.3 Implement `diff_listing(local: dict, remote: dict, pull_metadata: dict) -> ListingDiff` — field-by-field comparison
- [ ] 1.4 Handle type coercion edge cases (e.g., TOML integers vs API floats for price, list ordering for tags)
- [ ] 1.5 Implement conflict detection: compare `last_modified_tsz` from pull metadata vs live API value
- [ ] 1.6 Create `tests/test_diff.py` — unit tests for field comparison, conflict detection, type coercion, empty diffs

## 2. Diff Display

- [ ] 2.1 Create `etsync/listings/display.py` with `format_diff(diff: ListingDiff) -> str` for color-coded output
- [ ] 2.2 Implement summary mode: truncate long text fields (description), show `[changed, N chars added/removed]`
- [ ] 2.3 Implement verbose mode: show full field values for all fields
- [ ] 2.4 Implement conflict warning display
- [ ] 2.5 Implement overall summary formatter: `N listings changed, M conflicts, K unchanged`

## 3. Confirmation Flow

- [ ] 3.1 Implement confirmation prompt in `display.py`: `apply all (y) / reject all (n) / listing-by-listing (l)`
- [ ] 3.2 Implement per-listing prompt: `apply (y) / skip (s) / abort remaining (n)`
- [ ] 3.3 Skip confirmation in `--dry-run` mode
- [ ] 3.4 Skip conflicted listings by default, include with `--force`

## 4. Backup

- [ ] 4.1 Create `etsync/listings/backup.py` with `backup_remote_state(listing: dict, data_dir: Path) -> Path`
- [ ] 4.2 Save to `{data_dir}/listings/.backups/{listing_id}_{timestamp}.toml`
- [ ] 4.3 Ensure `.backups/` directory is created on first use

## 5. Push Implementation

- [ ] 5.1 Create `etsync/listings/push.py` with the main `push_listings()` function
- [ ] 5.2 Load local listing files from `{data_dir}/listings/*.toml`
- [ ] 5.3 Load pull metadata from `index.toml` for conflict detection
- [ ] 5.4 Fetch live listings from API for comparison
- [ ] 5.5 Compute diffs using the diff engine
- [ ] 5.6 Display diffs and handle confirmation flow
- [ ] 5.7 Call `EtsyAPI.update_listing()` for each confirmed listing with only changed fields
- [ ] 5.8 Implement retry with exponential backoff for rate-limited requests (429)
- [ ] 5.9 Report per-listing results (success/failure with error details)
- [ ] 5.10 Print final summary: `N updated, M skipped, K failed`
- [ ] 5.11 Refresh `index.toml` with updated `last_modified_tsz` for successfully pushed listings

## 6. CLI Integration

- [ ] 6.1 Add `push` Typer group in `etsync/cli.py`
- [ ] 6.2 Register `listings` subcommand under `push` group from `etsync/listings/push.py`
- [ ] 6.3 Add CLI options: `--id`, `--dry-run`, `--force`, `--verbose`
- [ ] 6.4 Verify `etsync push --help` and `etsync push listings --help` output

## 7. Pull Metadata Enhancement

- [ ] 7.1 Modify `etsync/listings/pull.py` to record `last_modified_tsz` per listing in `index.toml` under a `pull_metadata` section
- [ ] 7.2 Record pull timestamp in `index.toml` metadata
- [ ] 7.3 Ensure backward compatibility — push gracefully handles `index.toml` without `pull_metadata` (treat as no conflict data)

## 8. Tests

- [ ] 8.1 Create `tests/test_push.py` — end-to-end push tests with mocked API
- [ ] 8.2 Test: successful push with changes detected and applied
- [ ] 8.3 Test: no changes detected, clean exit
- [ ] 8.4 Test: dry-run mode prints diff without applying
- [ ] 8.5 Test: conflict detected, listing skipped by default
- [ ] 8.6 Test: conflict with `--force` flag, listing pushed anyway
- [ ] 8.7 Test: single listing push with `--id`
- [ ] 8.8 Test: user cancellation (reject all)
- [ ] 8.9 Test: partial failure — some listings succeed, some fail
- [ ] 8.10 Test: API rate limit triggers retry
- [ ] 8.11 Test: backup files created before push
- [ ] 8.12 Test: index.toml updated after successful push

## 9. Finalize

- [ ] 9.1 Run `ruff check .` — no lint errors
- [ ] 9.2 Run `ruff format --check .` — no format issues
- [ ] 9.3 Run `ty check` — no type errors
- [ ] 9.4 Run `pytest` — all tests pass
- [ ] 9.5 Manual smoke test: edit a local listing TOML, run `etsync push listings --dry-run`, verify diff output
- [ ] 9.6 Manual smoke test: push a real change to a test listing on Etsy
