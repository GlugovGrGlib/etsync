import typer


def register_commands(pull_app: typer.Typer) -> None:
    from etsync.analytics.pull import pull_reviews_command, pull_stats_command

    pull_app.command(name="stats")(pull_stats_command)
    pull_app.command(name="reviews")(pull_reviews_command)


def register_analytics_commands(analytics_app: typer.Typer) -> None:
    from etsync.analytics.query import (
        revenue_command,
        reviews_command,
        sales_command,
        top_listings_command,
    )

    analytics_app.command(name="top-listings")(top_listings_command)
    analytics_app.command(name="revenue")(revenue_command)
    analytics_app.command(name="reviews")(reviews_command)
    analytics_app.command(name="sales")(sales_command)
