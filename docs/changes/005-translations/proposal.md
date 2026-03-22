# Proposal: Listing Translations Management

## Intent

EU shops need listings translated into local languages (German, French, etc.) to rank well in Etsy search and convert local buyers. Etsy supports per-listing translations via the API, but `etsync` currently ignores them — `pull listings` only fetches the default-language data, and there's no way to push translations.

This change adds translation pull and push so the full translation workflow is scriptable: pull existing translations, edit them locally, push updates back.

## Scope

### In scope

- `etsync pull translations` — for each listing, fetch translations for configured languages and save as JSON files alongside the listing
- `etsync push translations` — read local translation files and create/update them on Etsy via the API
- Configurable target languages via `settings.toml` (e.g., `languages = ["de", "fr"]`)
- Translation files stored as `{data_dir}/listings/{listing_id}/translations/{language}.json`
- Single-listing operations (`--id <listing_id>`)
- Dry-run mode for push (`--dry-run`)

### Out of scope

- Automatic/machine translation of content
- Translation validation or completeness checks
- Shop-level translation settings
- Non-listing translations (shop description, policies, etc.)

## Approach

1. **Configuration** — Add `languages` list to `settings.toml` (e.g., `languages = ["de", "fr"]`). Empty list means skip translations.

2. **Pull** — For each listing in the index, call `get_listing_translation(shop_id, listing_id, language)` per configured language. Save each response as `{listing_id}/translations/{language}.json`. Translations that don't exist yet return a 404 — skip silently.

3. **Push** — For each local translation file, compare against the remote translation. If no remote translation exists, call `create_listing_translation`. If it exists, call `update_listing_translation`. Both `create` and `update` are unimplemented in `etsyv3`, so we call the Etsy API directly using the existing session (PUT endpoint: `/shops/{shop_id}/listings/{listing_id}/translations/{language}`).

4. **File layout** — Restructure listing storage from flat files to directories:
   - `{data_dir}/listings/{listing_id}.json` → `{data_dir}/listings/{listing_id}/listing.json`
   - `{data_dir}/listings/{listing_id}/translations/de.json`
   - `{data_dir}/listings/{listing_id}/translations/fr.json`
   - `{data_dir}/listings/index.json` stays at the top level

5. **Integration with existing pull** — `etsync pull listings` gains a `--with-translations` flag that also fetches translations in the same run. `etsync pull translations` is the standalone command.

## Future

These will become separate OpenSpec changes:

- **Translation templates** — generate blank translation files from listings for bulk translation workflows
- **Translation completeness report** — show which listings are missing translations for which languages
- **Auto-translate** — integrate with a translation API for draft translations
