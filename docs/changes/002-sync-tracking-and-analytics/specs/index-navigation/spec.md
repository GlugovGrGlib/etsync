# Spec: JSON Index Navigation

## ADDED Requirements

### Index JSON MUST be generated after each listings pull

**Scenario: Successful index generation**
- Given valid authentication tokens
- And the shop has active listings
- When the user runs `etsync pull listings`
- Then an `index.json` is created at `{data_dir}/listings/index.json`
- And it contains `shop_id`, `synced_at`, `listing_count`, and a `listings` array
- And the existing `index.toml` is still generated as before

**Scenario: Index contains rich metadata per listing**
- Given a successful listings pull
- When `index.json` is generated
- Then each listing entry contains: `listing_id`, `title`, `url`, `state`, `creation_tsz`, `last_modified_tsz`, `price` (with `amount`, `divisor`, `currency_code`), `quantity`, `tags` (array), `taxonomy_path` (array), `views`, `num_favorers`, `featured_rank`, `original_creation_tsz`, `shop_section_id`, `processing_min`, `processing_max`

**Scenario: Listing URL is constructed correctly**
- Given a listing with `listing_id` 1234567890
- When the index entry is built
- Then `url` is `https://www.etsy.com/listing/1234567890`

**Scenario: Empty shop**
- Given valid tokens but no active listings
- When the user runs `etsync pull listings`
- Then `index.json` is created with `listing_count: 0` and an empty `listings` array

### Listing URL format MUST follow Etsy conventions

**Scenario: URL construction**
- Given any listing in the index
- Then the `url` field is `https://www.etsy.com/listing/{listing_id}`
- And this URL is navigable in a browser to view the listing

### Price MUST use Etsy Money format

**Scenario: Price representation**
- Given a listing with a price of EUR 24.99
- When the index entry is built
- Then `price.amount` is `2499`, `price.divisor` is `100`, `price.currency_code` is `"EUR"`

### The `etsync list` command MUST browse index data

**Scenario: List all listings**
- Given an `index.json` exists in the data directory
- When the user runs `etsync list`
- Then all listings are displayed in a tabular format showing listing_id, title, price, views, favorites

**Scenario: Filter by tag**
- Given an `index.json` with listings tagged "ceramic" and "wood"
- When the user runs `etsync list --tag ceramic`
- Then only listings with the "ceramic" tag are shown

**Scenario: Filter by minimum price**
- Given an `index.json` with listings at various prices
- When the user runs `etsync list --min-price 20`
- Then only listings with price >= 20 (in the listing's currency) are shown

**Scenario: Sort listings**
- Given an `index.json` with multiple listings
- When the user runs `etsync list --sort views`
- Then listings are sorted by views in descending order

**Scenario: No index file**
- Given no `index.json` exists
- When the user runs `etsync list`
- Then a clear error instructs the user to run `etsync pull listings` first

### Index data MUST come from the listings API response

**Scenario: Data source**
- All index fields are sourced from the `GET /v3/application/shops/{shop_id}/listings/active` response
- The `etsyv3` method `EtsyAPI.get_shop_listing_active(shop_id, limit=100, offset=N)` is used
- No additional API calls are required for the base index (images are opt-in)

### Image metadata MUST be opt-in

**Scenario: Pull with images**
- When the user runs `etsync pull listings --include-images`
- Then for each listing, `GET /v3/application/listings/{listing_id}/images` is called
- And the first image URL is added to the index entry as `primary_image_url`

**Scenario: Pull without images (default)**
- When the user runs `etsync pull listings`
- Then no per-listing image API calls are made
- And `primary_image_url` is absent from index entries
