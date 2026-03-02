"""Display utilities using rich for formatted output."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult

console = Console()


def show_banner():
    banner = Text("DB Query Manager (dbqm)", style="bold cyan")
    console.print(Panel(banner, border_style="cyan", padding=(0, 2)))
    console.print()


def show_success(msg: str):
    console.print(f"  [green]v[/green] {msg}")


def show_error(msg: str):
    console.print(f"  [red]x[/red] {msg}")


def show_warning(msg: str):
    console.print(f"  [yellow]![/yellow] {msg}")


def show_info(msg: str):
    console.print(f"  [cyan]>[/cyan] {msg}")


def show_query_result(result: QueryResult):
    """Display a query result as a rich table."""
    if not result.success:
        show_error(f"Erro: {result.error}")
        return

    if not result.rows:
        show_warning("Nenhum registro retornado.")
        return

    table = Table(
        title=f"{result.query_name} ({result.connection_name})",
        show_lines=True,
        border_style="dim",
    )
    for col in result.columns:
        table.add_column(col, style="white")

    for row in result.rows:
        table.add_row(*[str(v) if v is not None else "" for v in row])

    console.print()
    console.print(table)
    console.print(
        f"\n  [dim]{result.row_count} registros | Tempo: {result.elapsed:.2f}s | Conexao: {result.connection_name}[/dim]\n"
    )


def show_group_result(group_result: GroupResult, params: dict | None = None):
    """Display full group comparison result with pivoted tables (one per key)."""
    query_names = list(group_result.query_results.keys())
    compare_columns = [c.column for c in group_result.comparisons]

    # Header
    console.print()
    console.rule("[bold cyan]RESULTADO COMPARATIVO[/bold cyan]", style="cyan")
    console.print(f"  [bold]Grupo:[/bold] {group_result.group_name}")
    if params:
        for k, v in params.items():
            console.print(f"  [bold]{k}:[/bold] {v}")
    console.print()

    # Per-query execution status
    for qname, qresult in group_result.query_results.items():
        if qresult.success:
            console.print(f"  [green]v[/green] {qname}: {qresult.row_count} registros ({qresult.elapsed:.2f}s)")
        else:
            console.print(f"  [red]x[/red] {qname}: ERRO - {qresult.error}")
    console.print()

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

    # Summary
    console.rule("[bold cyan]RESUMO[/bold cyan]", style="cyan")
    for comp in group_result.comparisons:
        _show_comparison_summary(comp)

    status_text = "[green]CONSISTENTE[/green]" if group_result.all_match else "[red]DIVERGENTE[/red]"
    console.print(f"\n  Resultado final: {status_text}")
    console.print()


def _status_cell(status: str) -> str:
    """Format a status value with color."""
    if status == "OK":
        return "[green]v OK[/green]"
    elif status == "OK*":
        return "[green]v OK*[/green]"
    elif status == "DIFF":
        return "[yellow]! DIFF[/yellow]"
    elif status == "ABSENT":
        return "[red]x AUSENTE[/red]"
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
        title=f"chave: {key_value}",
        show_lines=True,
        border_style="dim",
    )
    table.add_column("Consulta", style="bold")
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
                cells.append(str(v) if v is not None else "[dim]-[/dim]")
            else:
                cells.append("[dim]-[/dim]")
        cells.append("")  # no per-row status
        table.add_row(*cells)

    # Result row
    col_statuses = []
    for col in compare_columns:
        comp_row = lookup.get((key_value, col))
        status = comp_row.status if comp_row else "ABSENT"
        col_statuses.append(status)

    overall = _worst_status(col_statuses)
    result_cells = ["[bold]Resultado[/bold]"]
    for s in col_statuses:
        result_cells.append(_status_cell(s))
    result_cells.append(_status_cell(overall))

    table.add_section()
    table.add_row(*result_cells)

    console.print(table)
    console.print()


def _show_comparison_summary(comp: ComparisonResult):
    """Display summary stats for a comparison."""
    total = comp.total_keys
    console.print(f"  [bold]Coluna: {comp.column}[/bold]")
    console.print(f"    [green]v Iguais:[/green]      {comp.equal_count}/{total}")
    if comp.normalized_count > 0:
        console.print(f"    [green]v Normalizados:[/green] {comp.normalized_count}/{total}")
    console.print(f"    [yellow]! Diferentes:[/yellow]  {comp.diff_count}/{total}")
    console.print(f"    [red]x Ausentes:[/red]    {comp.absent_count}/{total}")

    if comp.absent_count > 0:
        for r in comp.rows:
            if r.status == "ABSENT":
                missing_in = [qn for qn, v in r.values.items() if v is None]
                if missing_in:
                    console.print(f"      chave {r.key_value}: ausente em {', '.join(missing_in)}")
