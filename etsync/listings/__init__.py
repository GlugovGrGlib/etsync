import typer


def register_commands(pull_app: typer.Typer) -> None:
    from etsync.listings.pull import pull_listings

    pull_app.command(name="listings")(pull_listings)
