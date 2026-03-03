"""Display utilities using rich for formatted output."""
from __future__ import annotations

import subprocess

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.syntax import Syntax

from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult

console = Console()


def clear_screen():
    """Clear terminal screen."""
    cmd = "cls" if __import__("os").name == "nt" else "clear"
    subprocess.run([cmd], shell=True, check=False)


def show_banner():
    clear_screen()
    width = min(console.width, 80)
    title = Text()
    title.append("🗄️  ", style="bold cyan")
    title.append("DB Query Manager", style="bold white")
    title.append("  (dbqm)", style="dim")
    console.print(Panel(
        title,
        border_style="cyan",
        padding=(1, 3),
        width=width,
        subtitle="[dim]ESC = voltar  |  ↑↓ = navegar  |  Enter = selecionar[/dim]",
        subtitle_align="center",
    ))
    console.print()


def show_success(msg: str):
    console.print(f"  [green]✅[/green] {msg}")


def show_error(msg: str):
    console.print(f"  [red]❌[/red] {msg}")


def show_warning(msg: str):
    console.print(f"  [yellow]⚠️ [/yellow] {msg}")


def show_info(msg: str):
    console.print(f"  [cyan]💡[/cyan] {msg}")


def show_query_result(result: QueryResult):
    """Display a query result as a rich table."""
    if not result.success:
        show_error(f"Erro: {result.error}")
        return

    if not result.rows:
        show_warning("Nenhum registro retornado.")
        return

    table = Table(
        title=f"📋 {result.query_name}",
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

    console.print()
    console.print(table)
    console.print(
        f"\n  [dim]📊 {result.row_count} registros  |  ⏱️  {result.elapsed:.2f}s  |  🔌 {result.connection_name}[/dim]\n"
    )


def _render_group_header(group_result: GroupResult, params: dict | None = None):
    """Render shared header for group result views."""
    console.print()
    console.rule("[bold cyan]📊 RESULTADO COMPARATIVO[/bold cyan]", style="cyan")
    console.print(f"  [bold]📁 Grupo:[/bold] {group_result.group_name}")
    if params:
        for k, v in params.items():
            console.print(f"  [bold]🏷️  {k}:[/bold] {v}")
    console.print()

    for qname, qresult in group_result.query_results.items():
        if qresult.success:
            console.print(f"  [green]✅[/green] {qname}: {qresult.row_count} registros ({qresult.elapsed:.2f}s)")
        else:
            console.print(f"  [red]❌[/red] {qname}: ERRO - {qresult.error}")
    console.print()


def _render_group_footer(group_result: GroupResult):
    """Render shared footer/summary for group result views."""
    console.rule("[bold cyan]📋 RESUMO[/bold cyan]", style="cyan")
    for comp in group_result.comparisons:
        _show_comparison_summary(comp)

    if group_result.all_match:
        status_text = "[green]✅ CONSISTENTE[/green]"
    else:
        status_text = "[red]❌ DIVERGENTE[/red]"
    console.print(f"\n  Resultado final: {status_text}")
    console.print()


def show_group_result(group_result: GroupResult, params: dict | None = None):
    """Display full group comparison result with pivoted tables (one per key)."""
    query_names = list(group_result.query_results.keys())
    compare_columns = [c.column for c in group_result.comparisons]

    _render_group_header(group_result, params)

    # Build lookup: {(key_value, column): ComparisonRow}
    lookup: dict[tuple, ComparisonRow] = {}
    all_keys: list = []
    for comp in group_result.comparisons:
        for row in comp.rows:
            lookup[(row.key_value, comp.column)] = row
            if row.key_value not in all_keys:
                all_keys.append(row.key_value)

    # One table per key
    for key in all_keys:
        _show_pivoted_key_table(key, query_names, compare_columns, lookup)

    _render_group_footer(group_result)


def _status_cell(status: str) -> str:
    """Format a status value with color and icon."""
    if status == "OK":
        return "[green]✅ OK[/green]"
    elif status == "OK*":
        return "[green]✅ OK*[/green]"
    elif status == "DIFF":
        return "[yellow]⚠️  DIFF[/yellow]"
    elif status == "ABSENT":
        return "[red]❌ AUSENTE[/red]"
    return status


def _worst_status(statuses: list[str]) -> str:
    """Return the worst status from a list (ABSENT > DIFF > OK* > OK)."""
    priority = {"ABSENT": 3, "DIFF": 2, "OK*": 1, "OK": 0}
    worst = max(statuses, key=lambda s: priority.get(s, 0))
    return worst


def _show_pivoted_key_table(
    key_value,
    query_names: list[str],
    compare_columns: list[str],
    lookup: dict,
):
    """Display a pivoted table for a single join key value."""
    table = Table(
        title=f"🔑 chave: {key_value}",
        show_lines=True,
        border_style="bright_black",
        title_style="bold white",
        header_style="bold bright_white",
        expand=True,
    )
    table.add_column("Consulta", style="bold cyan")
    for col in compare_columns:
        table.add_column(col, style="white")
    table.add_column("status", justify="center")

    # One row per query
    for qname in query_names:
        cells = [qname]
        for col in compare_columns:
            comp_row = lookup.get((key_value, col))
            if comp_row:
                v = comp_row.values.get(qname)
                cells.append(str(v) if v is not None else "[dim]—[/dim]")
            else:
                cells.append("[dim]—[/dim]")
        cells.append("")
        table.add_row(*cells)

    # Result row
    col_statuses = []
    for col in compare_columns:
        comp_row = lookup.get((key_value, col))
        status = comp_row.status if comp_row else "ABSENT"
        col_statuses.append(status)

    overall = _worst_status(col_statuses)
    result_cells = ["[bold white]Resultado[/bold white]"]
    for s in col_statuses:
        result_cells.append(_status_cell(s))
    result_cells.append(_status_cell(overall))

    table.add_section()
    table.add_row(*result_cells)

    console.print(table)
    console.print()


def show_group_result_flat(group_result: GroupResult, params: dict | None = None):
    """Display group comparison in flat mode — one table per compare column.

    Layout: key | query1_value | query2_value | ... | Status
    Differences are highlighted with color.
    """
    query_names = list(group_result.query_results.keys())

    _render_group_header(group_result, params)

    # One table per compare column
    for comp in group_result.comparisons:
        _show_flat_column_table(comp, query_names)

    _render_group_footer(group_result)


def _flat_status_label(status: str) -> str:
    """User-friendly status label for flat mode."""
    if status == "OK":
        return "[green]Igual[/green]"
    elif status == "OK*":
        return "[green]Igual*[/green]"
    elif status == "DIFF":
        return "[bold yellow]Diferente[/bold yellow]"
    elif status == "ABSENT":
        return "[bold red]Ausente[/bold red]"
    return status


def _highlight_diff_values(values: dict[str, any], status: str) -> dict[str, str]:
    """Return formatted cell strings, highlighting values that differ from majority."""
    str_values = {qn: str(v) if v is not None else None for qn, v in values.items()}

    if status not in ("DIFF", "ABSENT"):
        # No highlighting needed
        return {qn: (sv if sv is not None else "[dim]—[/dim]") for qn, sv in str_values.items()}

    if status == "ABSENT":
        return {
            qn: (f"[red]{sv}[/red]" if sv is not None else "[red bold]—[/red bold]")
            for qn, sv in str_values.items()
        }

    # DIFF: find majority value, highlight minority
    present = {qn: sv for qn, sv in str_values.items() if sv is not None}
    from collections import Counter
    counts = Counter(present.values())
    majority_val = counts.most_common(1)[0][0] if counts else None

    result = {}
    for qn, sv in str_values.items():
        if sv is None:
            result[qn] = "[dim]—[/dim]"
        elif sv != majority_val:
            result[qn] = f"[bold red]{sv}[/bold red]"
        else:
            result[qn] = sv
    return result


def _show_flat_column_table(comp: ComparisonResult, query_names: list[str]):
    """Display a flat table for a single compare column."""
    # Determine join key column name from the first row
    table = Table(
        title=f"📊 {comp.column}",
        show_lines=True,
        border_style="bright_black",
        title_style="bold cyan",
        header_style="bold bright_white",
        expand=True,
    )

    # Build columns: key | query1 | query2 | ... | Status
    table.add_column("chave", style="bold white", no_wrap=True)
    for qn in query_names:
        table.add_column(qn, style="white")
    table.add_column("Status", justify="center", no_wrap=True)

    for row in comp.rows:
        highlighted = _highlight_diff_values(row.values, row.status)
        cells = [str(row.key_value)]
        for qn in query_names:
            cells.append(highlighted.get(qn, "[dim]—[/dim]"))
        cells.append(_flat_status_label(row.status))
        table.add_row(*cells)

    console.print(table)
    console.print()


def _show_comparison_summary(comp: ComparisonResult):
    """Display summary stats for a comparison."""
    total = comp.total_keys
    console.print(f"  [bold]📊 Coluna: {comp.column}[/bold]")
    console.print(f"    [green]✅ Iguais:[/green]      {comp.equal_count}/{total}")
    if comp.normalized_count > 0:
        console.print(f"    [green]✅ Normalizados:[/green] {comp.normalized_count}/{total}")
    console.print(f"    [yellow]⚠️  Diferentes:[/yellow]  {comp.diff_count}/{total}")
    console.print(f"    [red]❌ Ausentes:[/red]    {comp.absent_count}/{total}")

    if comp.absent_count > 0:
        for r in comp.rows:
            if r.status == "ABSENT":
                missing_in = [qn for qn, v in r.values.items() if v is None]
                if missing_in:
                    console.print(f"      🔍 chave {r.key_value}: ausente em {', '.join(missing_in)}")


def show_browse_result(result):
    """Display a table browse result as a rich table."""
    from dbqm.core.table_browser import BrowseResult

    if not result.rows:
        show_warning("Tabela vazia.")
        return

    table = Table(
        title=f"📋 {result.table}",
        show_lines=True,
        border_style="bright_black",
        title_style="bold cyan",
        header_style="bold bright_white",
        expand=True,
    )

    for col in result.columns:
        style = "cyan" if col in result.fk_columns else "white"
        table.add_column(col, style=style)

    for row in result.rows:
        table.add_row(*[str(v) if v is not None else "" for v in row])

    console.print()
    console.print(table)

    page_start = result.offset + 1
    page_end = result.offset + result.row_count
    console.print(
        f"\n  [dim]📊 {page_start}-{page_end} de {result.total_count} registros  "
        f"|  ⏱️  {result.elapsed:.2f}s  "
        f"|  🔌 {result.connection_name}  "
        f"|  📏 Limite: {result.limit}[/dim]\n"
    )


def show_table_structure(structure):
    """Display table structure (columns, indexes) as a rich table."""
    from dbqm.core.object_browser import TableStructure

    table = Table(
        title=f"🏗️  Estrutura: {structure.table}",
        show_lines=True,
        border_style="bright_black",
        title_style="bold cyan",
        header_style="bold bright_white",
        expand=True,
    )
    table.add_column("Coluna", style="bold white")
    table.add_column("Tipo", style="yellow")
    table.add_column("Tam.", style="white", justify="right")
    table.add_column("Null?", justify="center")
    table.add_column("Chave", style="white")

    for col in structure.columns:
        # Format size: data_length for strings, precision,scale for numbers
        if col.data_precision is not None:
            size = f"{col.data_precision}"
            if col.data_scale is not None and col.data_scale > 0:
                size += f",{col.data_scale}"
        elif col.data_length is not None:
            size = str(col.data_length)
        else:
            size = ""

        # Nullable as colored Y/N
        nullable = "[green]Y[/green]" if col.nullable else "[red]N[/red]"

        # Key info
        key_parts = []
        if col.is_pk:
            key_parts.append("[yellow]PK[/yellow]")
        if col.fk_ref:
            key_parts.append(f"[cyan]FK -> {col.fk_ref}[/cyan]")
        key = " ".join(key_parts)

        table.add_row(col.name, col.data_type, size, nullable, key)

    console.print()
    console.print(table)

    # Show indexes
    if structure.indexes:
        console.print()
        console.print("  [bold]Indexes:[/bold]")
        for idx in structure.indexes:
            unique_tag = "[yellow]UNIQUE[/yellow] " if idx.is_unique else ""
            cols = ", ".join(idx.columns)
            console.print(f"    {unique_tag}[white]{idx.name}[/white] ({cols})")

    console.print(
        f"\n  [dim]📊 {structure.total_count} registros  |  ⏱️  {structure.elapsed:.2f}s[/dim]\n"
    )


def show_package_routines(info):
    """Display package routines (procedures and functions) as a rich table."""
    from dbqm.core.object_browser import PackageInfo

    console.print()
    console.rule(f"[bold cyan]📦 {info.name}[/bold cyan]", style="cyan")
    console.print()

    table = Table(
        show_lines=True,
        border_style="bright_black",
        header_style="bold bright_white",
        expand=True,
    )
    table.add_column("#", style="dim", justify="right", width=4)
    table.add_column("Tipo", width=12)
    table.add_column("Rotina", style="bold white")
    table.add_column("Parametros", style="dim")

    for i, routine in enumerate(info.routines, 1):
        if routine.routine_type == "FUNCTION":
            type_label = "[green]FUNCTION[/green]"
        else:
            type_label = "[blue]PROCEDURE[/blue]"

        table.add_row(str(i), type_label, routine.name, routine.signature)

    console.print(table)
    console.print(f"\n  [dim]Owner: {info.owner}[/dim]\n")


def show_view_definition(info):
    """Display view SQL definition with syntax highlighting."""
    from dbqm.core.object_browser import ViewInfo

    console.print()
    console.rule(f"[bold cyan]👁️  {info.name}[/bold cyan]", style="cyan")
    console.print()

    syntax = Syntax(
        info.sql_definition,
        "sql",
        theme="monokai",
        line_numbers=True,
    )
    console.print(syntax)

    console.print(f"\n  [dim]Owner: {info.owner}[/dim]\n")


def show_routine_result(result):
    """Display routine execution result (success/error with DBMS_OUTPUT)."""
    from dbqm.core.object_browser import RoutineExecutionResult

    console.print()
    if result.success:
        show_success(f"Executado com sucesso  ({result.elapsed:.2f}s)")
        if result.output_lines:
            console.print()
            console.print("  [bold]DBMS_OUTPUT:[/bold]")
            for line in result.output_lines:
                console.print(f"    {line}")
    else:
        show_error(f"{result.error}  ({result.elapsed:.2f}s)")
    console.print()


def show_source_code(title: str, source: str):
    """Display generic source code with syntax highlighting."""
    console.print()
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="cyan")
    console.print()

    syntax = Syntax(
        source,
        "sql",
        theme="monokai",
        line_numbers=True,
    )
    console.print(syntax)
    console.print()
