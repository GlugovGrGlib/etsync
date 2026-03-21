import typer


def register_commands(pull_app: typer.Typer) -> None:
    from etsync.analytics.pull import pull_stats

    pull_app.command(name="stats")(pull_stats)
