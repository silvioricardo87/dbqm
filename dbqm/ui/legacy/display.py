"""Rich renderable builders for PNG/TXT screenshot export.

These functions produce Rich renderable objects (Table, Panel, Syntax, Text)
consumed by ``dbqm.core.exporter.export_screenshot()``.  They were extracted
from the original ``dbqm.ui.display`` module so that the Textual UI does not
depend on the legacy Rich console helpers.
"""
from __future__ import annotations

from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

from dbqm.core.query_engine import QueryResult


def _build_params_table(params: dict) -> Panel:
    """Build a compact table displaying query parameters."""
    tbl = Table(
        show_header=False,
        show_lines=False,
        border_style="cyan",
        box=None,
        padding=(0, 2),
    )
    tbl.add_column("param", style="bold cyan", no_wrap=True)
    tbl.add_column("sep", style="dim", width=1)
    tbl.add_column("value", style="bold white")
    for k, v in params.items():
        tbl.add_row(k, "=", str(v))
    return Panel(tbl, title="[bold cyan]Parametros[/bold cyan]", border_style="cyan", expand=True)


def build_individual_renderables(result: QueryResult, sql: str, params: dict | None = None) -> list:
    """Build renderable objects for individual result (used by screenshot export)."""
    renderables: list = []

    formatted_sql = sql.strip()
    if params:
        renderables.append(_build_params_table(params))

    syntax = Syntax(formatted_sql, "sql", theme="monokai", line_numbers=True)
    renderables.append(Panel(syntax, title="[bold cyan]SQL[/bold cyan]", border_style="cyan", expand=True))

    if result.rows:
        table = Table(
            title=f"\U0001f4cb {result.query_name} (dados brutos)",
            show_lines=True,
            border_style="bright_black",
            title_style="bold cyan",
            header_style="bold bright_white",
            expand=True,
        )
        for col in result.columns:
            table.add_column(col, style="white")
        for row in result.rows:
            table.add_row(*[str(v) if v is not None else "" for v in row])
        renderables.append(table)

    renderables.append(Text(
        f"\n  \U0001f4ca {result.row_count} registros  |  \u23f1\ufe0f  {result.elapsed:.2f}s  |  \U0001f50c {result.connection_name}\n",
        style="dim",
    ))
    return renderables


def build_query_renderables(result: QueryResult, params: dict | None = None) -> list:
    """Build renderable objects for a single query result (used by screenshot export)."""
    renderables: list = []

    if params:
        renderables.append(_build_params_table(params))

    if result.rows:
        table = Table(
            title=f"\U0001f4cb {result.query_name}",
            show_lines=True,
            border_style="bright_black",
            title_style="bold cyan",
            header_style="bold bright_white",
            expand=True,
        )
        for col in result.columns:
            table.add_column(col, style="white")
        for row in result.rows:
            table.add_row(*[str(v) if v is not None else "" for v in row])
        renderables.append(table)

    renderables.append(Text(
        f"\n  \U0001f4ca {result.row_count} registros  |  \u23f1\ufe0f  {result.elapsed:.2f}s  |  \U0001f50c {result.connection_name}\n",
        style="dim",
    ))
    return renderables
