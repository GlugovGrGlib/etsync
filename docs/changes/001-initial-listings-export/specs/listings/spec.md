# Spec: Initial Listings Export

## ADDED Requirements

### Configuration MUST load from dynaconf settings

**Scenario: Valid configuration**
- Given a `settings.toml` with `shop_id`, `api_base_url`, and `data_dir`
- And a `.secrets.toml` with `api_keystring`
- When the application starts
- Then settings are available via the `settings` object
- And `data_dir` defaults to `~/.etsync/data/` if not specified

**Scenario: Missing required config**
- Given `settings.toml` is missing `shop_id`
- When the application starts
- Then a validation error is raised with a clear message

**Scenario: Multi-shop environments**
- Given `settings.toml` defines environments `[shop1]` and `[shop2]`
- When `ETSYNC_ENV=shop2` is set
- Then settings for `shop2` are loaded (its own `shop_id`, `data_dir`, tokens)

### Authentication MUST use OAuth 2.0 via etsyv3

**Scenario: First-time login**
- Given no tokens exist in `.secrets.toml`
- When the user runs `etsync login`
- Then the browser opens for Etsy OAuth consent
- And after approval, `access_token`, `refresh_token`, and `expires_at` are saved to `.secrets.toml`

**Scenario: Token refresh**
- Given an expired `access_token` with a valid `refresh_token`
- When any API call is made
- Then `etsyv3.EtsyAPI` refreshes the token automatically
- And the new tokens are persisted via the `refresh_save` callback

### Listings pull MUST download all active listings as TOML

**Scenario: Successful pull**
- Given valid authentication tokens
- And the shop has active listings
- When the user runs `etsync pull listings`
- Then all active listings are fetched (handling pagination)
- And each listing is saved as `{data_dir}/listings/{listing_id}.toml`
- And an `index.toml` is created with a summary of all listings

**Scenario: Pagination**
- Given the shop has more than 100 active listings
- When the user runs `etsync pull listings`
- Then multiple API pages are fetched transparently
- And all listings are saved

**Scenario: No authentication**
- Given no valid tokens exist
- When the user runs `etsync pull listings`
- Then a clear error is shown instructing the user to run `etsync login` first

**Scenario: Empty shop**
- Given valid tokens but no active listings
- When the user runs `etsync pull listings`
- Then `index.toml` is created with an empty listings array
- And a message indicates no listings were found

### CLI MUST provide concise commands

**Scenario: Help output**
- Given `etsync` is installed
- When the user runs `etsync --help`
- Then available commands are listed: `login`, `pull`

**Scenario: Pull subcommands**
- When the user runs `etsync pull --help`
- Then available domains are listed (currently: `listings`)
