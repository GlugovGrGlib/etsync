"""Query helper for the analytics DuckDB database."""

from pathlib import Path

import duckdb
import typer


def run_query(db_path: Path, sql: str) -> tuple[list[str], list[tuple]]:  # type: ignore[type-arg]
    """Open the DuckDB and execute a SQL query. Returns (columns, rows)."""
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        result = con.execute(sql)
        columns: list[str] = [desc[0] for desc in result.description]
        rows: list[tuple] = result.fetchall()  # type: ignore[type-arg]
    finally:
        con.close()
    return columns, rows


def format_table(columns: list[str], rows: list[tuple]) -> str:  # type: ignore[type-arg]
    """Format query results as a simple text table."""
    if not rows:
        return "(no results)"

    str_rows = [[str(v) for v in row] for row in rows]
    widths = [max(len(col), *(len(r[i]) for r in str_rows)) for i, col in enumerate(columns)]

    header = " | ".join(col.ljust(w) for col, w in zip(columns, widths))
    separator = "-+-".join("-" * w for w in widths)
    body_lines = [" | ".join(val.ljust(w) for val, w in zip(row, widths)) for row in str_rows]

    return "\n".join([header, separator, *body_lines])


def query_command(sql: str = typer.Argument(help="SQL query to run against the analytics database")) -> None:
    """Run a SQL query against the analytics DuckDB."""
    from etsync.config import get_data_dir

    db_path = get_data_dir() / "analytics.db"
    if not db_path.exists():
        typer.echo(f"Analytics database not found at {db_path}. Run 'etsync pull stats' first.", err=True)
        raise typer.Exit(code=1)

    columns, rows = run_query(db_path, sql)
    typer.echo(format_table(columns, rows))
