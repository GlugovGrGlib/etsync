# Spec: Listing Translations Management

## ADDED Requirements

### Configuration MUST support a languages list

**Scenario: Languages configured**
- Given `settings.toml` contains `languages = ["de", "fr"]`
- When any translation command runs
- Then it operates on German and French translations

**Scenario: No languages configured**
- Given `settings.toml` has `languages = []` or the key is absent
- When `etsync pull translations` runs
- Then it exits with a message: "No languages configured in settings.toml"

### Pull translations MUST fetch and save per-listing translation files

**Scenario: Successful pull**
- Given valid auth tokens and `languages = ["de", "fr"]`
- And listing 123 has a German translation on Etsy
- When the user runs `etsync pull translations`
- Then `{data_dir}/listings/123/translations/de.json` is created with the translation data
- And no `fr.json` is created for listing 123 (404 skipped silently)

**Scenario: Single listing pull**
- Given `--id 123` is passed
- When the user runs `etsync pull translations --id 123`
- Then only listing 123's translations are fetched

**Scenario: No index exists**
- Given no `index.json` exists in the listings directory
- When the user runs `etsync pull translations`
- Then an error is shown: "No listings index found. Run `etsync pull listings` first."

### Push translations MUST create or update remote translations

**Scenario: Create new translation**
- Given `{data_dir}/listings/123/translations/de.json` exists locally
- And listing 123 has no German translation on Etsy
- When the user runs `etsync push translations`
- Then a POST request creates the German translation for listing 123

**Scenario: Update existing translation**
- Given `{data_dir}/listings/123/translations/de.json` exists locally
- And listing 123 already has a German translation on Etsy
- And the local content differs from remote
- When the user runs `etsync push translations`
- Then a PUT request updates the German translation for listing 123

**Scenario: No changes**
- Given local and remote translations are identical
- When the user runs `etsync push translations`
- Then the listing is skipped with no API write call

**Scenario: Dry run**
- Given local translations differ from remote
- When the user runs `etsync push translations --dry-run`
- Then diffs are printed but no API calls are made

**Scenario: Single listing push**
- Given `--id 123` is passed
- When the user runs `etsync push translations --id 123`
- Then only listing 123's translations are pushed

### Listing storage MUST migrate to nested directory layout

**Scenario: Fresh pull after migration**
- Given listings were previously stored as `{listing_id}.json` (flat)
- When the user runs `etsync pull listings`
- Then listings are saved as `{listing_id}/listing.json` (nested)
- And old flat files are not deleted (user can clean up manually)

**Scenario: Index remains at top level**
- When listings are pulled
- Then `index.json` stays at `{data_dir}/listings/index.json`

## CHANGED Requirements

### Pull listings MUST support --with-translations flag

**Scenario: Pull with translations**
- Given `languages = ["de"]` in settings
- When the user runs `etsync pull listings --with-translations`
- Then listings are pulled as usual
- And translations are also fetched for each listing

**Scenario: Pull without flag**
- When the user runs `etsync pull listings` (no flag)
- Then only listings are pulled, no translations
