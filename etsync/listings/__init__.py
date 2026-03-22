import typer


def register_commands(pull_app: typer.Typer) -> None:
    from etsync.listings.pull import pull_listings
    from etsync.listings.translations import pull_translations

    pull_app.command(name="listings")(pull_listings)
    pull_app.command(name="translations")(pull_translations)


def register_push_commands(push_app: typer.Typer) -> None:
    from etsync.listings.push import push_listings
    from etsync.listings.translations import push_translations

    push_app.command(name="listings")(push_listings)
    push_app.command(name="translations")(push_translations)
