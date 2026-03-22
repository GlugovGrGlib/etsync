# Tasks: Listing Translations Management

## 1. Configuration

- [ ] 1.1 Add `languages` setting to `settings.toml` (default `[]`)
- [ ] 1.2 Update `config.py` to expose `languages` with a default empty list

## 2. Listing Storage Migration

- [ ] 2.1 Update `pull.py` to save listings as `{listing_id}/listing.json` instead of `{listing_id}.json`
- [ ] 2.2 Update any code that reads listing files to use the new nested path
- [ ] 2.3 Update existing tests for the new directory layout

## 3. Pull Translations

- [ ] 3.1 Create `etsync/listings/translations.py` with `pull_translations()` function
- [ ] 3.2 Implement per-listing, per-language GET with 404 handling
- [ ] 3.3 Save translations to `{listing_id}/translations/{language}.json`
- [ ] 3.4 Support `--id` flag for single-listing pull
- [ ] 3.5 Register `translations` command under `pull` group in CLI
- [ ] 3.6 Add `--with-translations` flag to `pull listings`

## 4. Push Translations

- [ ] 4.1 Implement direct API calls for create (POST) and update (PUT) translations
- [ ] 4.2 Implement `push_translations()` — scan local files, diff vs remote, create/update
- [ ] 4.3 Support `--id` flag for single-listing push
- [ ] 4.4 Support `--dry-run` flag
- [ ] 4.5 Register `translations` command under `push` group in CLI

## 5. Tests

- [ ] 5.1 Create `tests/test_translations.py`
- [ ] 5.2 Test pull: successful fetch, 404 skip, no-languages error, single-listing mode
- [ ] 5.3 Test push: create, update, skip-unchanged, dry-run
- [ ] 5.4 Test storage migration: nested layout, index location

## 6. Finalize

- [ ] 6.1 Run `ruff check`, `ruff format --check`, `ty check`
- [ ] 6.2 Run `pytest` — all tests pass
- [ ] 6.3 Manual smoke test with a real listing
