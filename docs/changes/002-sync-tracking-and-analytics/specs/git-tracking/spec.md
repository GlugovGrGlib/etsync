# Spec: Git-Based Sync Tracking

## ADDED Requirements

### Data directory MUST be initialized as a git repo on first sync

**Scenario: First-time pull**
- Given the data directory exists at `{data_dir}`
- And it is not yet a git repository
- When the user runs `etsync pull listings`
- Then a git repository is initialized in `{data_dir}`
- And a `.gitignore` is created excluding `analytics.duckdb` and `analytics.duckdb.wal`
- And the initial commit is created

**Scenario: Subsequent pull**
- Given the data directory is already a git repository
- When the user runs `etsync pull listings`
- Then no re-initialization occurs
- And the existing repo is reused

### Every successful sync MUST create a git commit

**Scenario: Listings pull commit**
- Given a successful `etsync pull listings` that downloaded N listings
- Then all changes in the data directory are staged
- And a commit is created with message `sync: {ISO 8601 timestamp} — {N} listings`

**Scenario: Stats pull commit**
- Given a successful `etsync pull stats`
- Then a commit is created with message `stats: {ISO 8601 timestamp}`

**Scenario: No changes**
- Given a `etsync pull listings` where no listing data has changed since the last sync
- Then no commit is created (working tree is clean)
- And a message indicates nothing has changed

### Commit messages MUST follow a consistent format

**Scenario: Listings sync message**
- Format: `sync: 2026-03-21T14:30:00 — 47 listings`
- The timestamp is the time the sync completed (local time, ISO 8601)
- The count reflects the total number of listings in the pull

**Scenario: Stats sync message**
- Format: `stats: 2026-03-21T14:30:00`

### The `etsync diff` command MUST show changes between syncs

**Scenario: Default diff (last two syncs)**
- Given at least two commits in the data repo
- When the user runs `etsync diff`
- Then the diff between the most recent commit and the one before it is displayed
- And the output shows added, modified, and deleted listing files

**Scenario: Diff between specific commits**
- Given commit hashes `abc123` and `def456` in the data repo
- When the user runs `etsync diff --from abc123 --to def456`
- Then the diff between those two commits is displayed

**Scenario: No history**
- Given only one commit (or no commits) in the data repo
- When the user runs `etsync diff`
- Then a message indicates insufficient sync history to diff

**Scenario: Diff shows listing content changes**
- Given a listing title changed between two syncs
- When `etsync diff` is run
- Then the TOML diff shows the old and new title values

### The `etsync log` command MUST show sync history

**Scenario: Default log**
- Given multiple syncs have been performed
- When the user runs `etsync log`
- Then the last 10 commits are shown with hash (short), date, and message

**Scenario: Custom count**
- When the user runs `etsync log --limit 5`
- Then only the last 5 commits are shown

**Scenario: No repo**
- Given no data directory or no git repo initialized
- When the user runs `etsync log`
- Then a clear error instructs the user to run a sync first

### DuckDB files MUST be excluded from git tracking

**Scenario: .gitignore content**
- Given the data repo is initialized
- Then `.gitignore` contains `analytics.duckdb` and `analytics.duckdb.wal`
- And these files are never staged or committed

### Git operations MUST NOT fail the sync

**Scenario: Git error during commit**
- Given a successful listings pull
- And the git commit fails for any reason (e.g., permissions, corrupt repo)
- Then the sync itself is still considered successful
- And a warning is printed that version tracking failed
- And the downloaded TOML files are intact
