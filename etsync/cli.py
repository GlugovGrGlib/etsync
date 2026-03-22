import typer

app = typer.Typer(help="etsync — scriptable Etsy shop management")
pull_app = typer.Typer(help="Pull data from Etsy")
push_app = typer.Typer(help="Push local changes to Etsy")
diff_app = typer.Typer(help="Show changes between syncs")
analytics_app = typer.Typer(help="Pre-built analytics queries")

app.add_typer(pull_app, name="pull")
app.add_typer(push_app, name="push")
app.add_typer(diff_app, name="diff")
app.add_typer(analytics_app, name="analytics")


@app.command()
def login() -> None:
    """Authenticate with Etsy via OAuth 2.0."""
    from etsync.auth import login as do_login

    do_login()


@app.command()
def query(sql: str = typer.Argument(help="SQL query to run against the analytics database")) -> None:
    """Run a SQL query against the analytics DuckDB."""
    from etsync.analytics.query import query_command

    query_command(sql)


@diff_app.command("listings")
def diff_listings() -> None:
    """Show changes in listings since the last sync."""
    from etsync.config import get_data_dir
    from etsync.data_repo import diff_last_sync

    data_dir = get_data_dir()
    output = diff_last_sync(data_dir)
    typer.echo(output)


# Register domain subcommands
from etsync.listings import register_commands, register_push_commands  # noqa: E402
from etsync.analytics import register_analytics_commands, register_commands as register_analytics  # noqa: E402

register_commands(pull_app)
register_push_commands(push_app)
register_analytics(pull_app)
register_analytics_commands(analytics_app)
