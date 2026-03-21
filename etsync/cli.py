import typer

app = typer.Typer(help="etsync — scriptable Etsy shop management")
pull_app = typer.Typer(help="Pull data from Etsy")
app.add_typer(pull_app, name="pull")


@app.command()
def login() -> None:
    """Authenticate with Etsy via OAuth 2.0."""
    from etsync.auth import login as do_login

    do_login()


# Register domain subcommands
from etsync.listings import register_commands  # noqa: E402

register_commands(pull_app)
