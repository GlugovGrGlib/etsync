# Spec: Listings Push

## ADDED Requirements

### Push MUST compare local state against live API state

**Scenario: Successful push with changes**
- Given valid authentication tokens
- And a local listing file `{data_dir}/listings/12345.toml` with `title` changed to "Updated Title"
- When the user runs `etsync push listings`
- Then the command fetches listing 12345 from the Etsy API
- And displays a diff showing the title change: `title: "Old Title" -> "Updated Title"`
- And prompts for confirmation
- When the user confirms with `y`
- Then `update_listing(12345, title="Updated Title")` is called with only the changed field
- And the output shows `1 updated, 0 skipped, 0 failed`
- And `index.toml` is refreshed with the new `last_modified_tsz`

**Scenario: No changes detected**
- Given valid authentication tokens
- And all local listing files match the current API state
- When the user runs `etsync push listings`
- Then the output shows "No changes detected."
- And no API update calls are made
- And no confirmation prompt is shown

### Push MUST detect conflicts with remote changes

**Scenario: Conflict detected — listing modified on Etsy since last pull**
- Given a local listing file for listing 12345
- And `index.toml` records `last_modified_tsz = 1710000000` from the last pull
- And the live API returns `last_modified_tsz = 1710100000` (modified after pull)
- When the user runs `etsync push listings`
- Then the diff output shows a conflict warning: `CONFLICT: listing was modified on Etsy since last pull`
- And listing 12345 is skipped by default
- And the output shows `0 updated, 1 skipped (conflict), 0 failed`

**Scenario: Conflict with --force flag**
- Given the same conflict scenario as above
- When the user runs `etsync push listings --force`
- Then the conflict warning is shown but the listing is not skipped
- And the user is prompted for confirmation
- When the user confirms
- Then the update is applied despite the conflict

**Scenario: No pull metadata available**
- Given a local listing file for listing 12345
- And `index.toml` has no `pull_metadata` section (pulled before this feature)
- When the user runs `etsync push listings`
- Then conflict detection is skipped for that listing (no baseline to compare)
- And a warning is shown: `No pull metadata for listing 12345; conflict detection unavailable. Re-pull to enable.`

### Dry-run mode MUST show changes without applying

**Scenario: Dry-run with changes**
- Given local listings with modifications
- When the user runs `etsync push listings --dry-run`
- Then the diff is displayed with all changed fields
- And no confirmation prompt is shown
- And no API update calls are made
- And the command exits with code 0

**Scenario: Dry-run with no changes**
- Given all local listings match the API state
- When the user runs `etsync push listings --dry-run`
- Then the output shows "No changes detected."
- And the command exits with code 0

### Single listing push MUST target only the specified listing

**Scenario: Push single listing by ID**
- Given local listing files for listings 12345, 67890, and 11111
- And listings 12345 and 67890 have local changes
- When the user runs `etsync push listings --id 12345`
- Then only listing 12345 is compared and diffed
- And listing 67890 is not mentioned or processed
- And after confirmation, only listing 12345 is updated

**Scenario: Push single listing — ID not found locally**
- Given no local listing file exists for listing 99999
- When the user runs `etsync push listings --id 99999`
- Then an error is shown: `Listing 99999 not found in {data_dir}/listings/`
- And available listing IDs are listed
- And the command exits with code 1

### User MUST be able to cancel the push

**Scenario: User rejects all changes**
- Given local listings with modifications
- And the diff is displayed
- When the user is prompted and responds with `n`
- Then no API update calls are made
- And the output shows "Push cancelled."

**Scenario: User reviews listing-by-listing**
- Given local listings 12345 and 67890 both have changes
- And the diff is displayed
- When the user responds with `l` (listing-by-listing)
- Then the user is prompted for listing 12345: `apply (y) / skip (s) / abort remaining (n)`
- When the user responds `y` for 12345
- Then listing 12345 is updated
- When the user is prompted for listing 67890 and responds `s`
- Then listing 67890 is skipped
- And the output shows `1 updated, 1 skipped, 0 failed`

**Scenario: User aborts during listing-by-listing review**
- Given local listings 12345, 67890, and 11111 all have changes
- When the user is in listing-by-listing mode
- And responds `y` for 12345
- And responds `n` (abort remaining) at 67890
- Then only listing 12345 is updated
- And listings 67890 and 11111 are not processed
- And the output shows `1 updated, 2 skipped, 0 failed`

### Push MUST handle partial failures gracefully

**Scenario: Some listings fail to update**
- Given local listings 12345 and 67890 both have confirmed changes
- And the API returns success for 12345
- And the API returns a 400 validation error for 67890
- Then listing 12345 is reported as successful
- And listing 67890 is reported as failed with the error message
- And the output shows `1 updated, 0 skipped, 1 failed`
- And `index.toml` is refreshed only for listing 12345

**Scenario: Rate limit encountered**
- Given a confirmed listing to push
- And the API returns a 429 rate limit response
- Then the command waits and retries with exponential backoff
- And retries up to 3 times
- If the retry succeeds, the listing is reported as updated
- If all retries fail, the listing is reported as failed

**Scenario: Listing deleted on Etsy**
- Given a local listing file for listing 12345
- And the API returns 404 when fetching listing 12345
- Then the listing is reported as failed: `Listing 12345 not found on Etsy (may have been deleted)`
- And the command continues processing remaining listings

### Backup MUST be created before pushing changes

**Scenario: Backup created**
- Given listing 12345 has confirmed changes to push
- Before the update API call is made
- Then the current remote state of listing 12345 is saved to `{data_dir}/listings/.backups/12345_{timestamp}.toml`

### CLI MUST provide appropriate subcommands

**Scenario: Push help output**
- When the user runs `etsync push --help`
- Then available domains are listed (currently: `listings`)

**Scenario: Push listings help output**
- When the user runs `etsync push listings --help`
- Then options are listed: `--id`, `--dry-run`, `--force`, `--verbose`

### Authentication MUST be validated before push

**Scenario: No authentication**
- Given no valid tokens exist
- When the user runs `etsync push listings`
- Then a clear error is shown instructing the user to run `etsync login` first
- And no listing files are read or processed
