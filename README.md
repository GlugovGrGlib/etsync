# etsync

CLI tool for managing your Etsy shop data locally. Pull listings from the Etsy API, store them as TOML files.

## Install

```bash
uv sync
```

## Setup

1. Create an Etsy API app at https://www.etsy.com/developers/your-apps and grab your API keystring.

2. Copy the settings template and fill in your details:

```bash
cp settings.toml.example settings.toml
```

Edit `settings.toml`:
```toml
shop_id = "YOUR_SHOP_ID"
```

Create `.secrets.toml` (never commit this):
```toml
api_keystring = "YOUR_API_KEY"
```

3. Authenticate:

```bash
etsync login
```

## Usage

```bash
etsync pull listings    # download all active listings to TOML
```

Listings are saved to `~/.etsync/data/listings/` by default. Change this with `data_dir` in `settings.toml`.

## Multi-shop

Set `ETSYNC_ENV` to switch between shop configs:

```bash
ETSYNC_ENV=shop2 etsync pull listings
```

Define per-shop settings in `settings.toml`:
```toml
[default]
shop_id = "111"

[shop2]
shop_id = "222"
data_dir = "~/.etsync/data-shop2/"
```
