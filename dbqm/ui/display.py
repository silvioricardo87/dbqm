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
    """Display full group comparison result."""
    query_names = list(group_result.query_results.keys())

    # Header
    console.print()
    console.rule("[bold cyan]RESULTADO COMPARATIVO[/bold cyan]", style="cyan")
    console.print(f"  [bold]Grupo:[/bold] {group_result.group_name}")
    if params:
        for k, v in params.items():
            console.print(f"  [bold]{k}:[/bold] {v}")
    console.print()

    # Per-query status
    for qname, qresult in group_result.query_results.items():
        if qresult.success:
            console.print(f"  [green]v[/green] {qname}: {qresult.row_count} registros ({qresult.elapsed:.2f}s)")
        else:
            console.print(f"  [red]x[/red] {qname}: ERRO - {qresult.error}")
    console.print()

    # Comparison tables
    for comp in group_result.comparisons:
        _show_comparison_table(comp, query_names)

    # Summary
    console.rule("[bold cyan]RESUMO[/bold cyan]", style="cyan")
    for comp in group_result.comparisons:
        _show_comparison_summary(comp, query_names, group_result)

    status_text = "[green]CONSISTENTE[/green]" if group_result.all_match else "[red]DIVERGENTE[/red]"
    console.print(f"\n  Resultado final: {status_text}")
    console.print()


def _show_comparison_table(comp: ComparisonResult, query_names: list[str]):
    """Display a single comparison column table."""
    table = Table(
        title=f"Comparacao: {comp.column}",
        show_lines=True,
        border_style="dim",
    )
    table.add_column("chave", style="bold")
    for qn in query_names:
        table.add_column(qn, style="white")
    table.add_column("status", justify="center")

    for row in comp.rows:
        vals = []
        vals.append(str(row.key_value))
        for qn in query_names:
            v = row.values.get(qn)
            vals.append(str(v) if v is not None else "[dim]-[/dim]")

        if row.status == "OK":
            status_cell = "[green]v OK[/green]"
        elif row.status == "OK*":
            status_cell = "[green]v OK*[/green]"
        elif row.status == "DIFF":
            status_cell = "[yellow]! DIFF[/yellow]"
        elif row.status == "ABSENT":
            status_cell = "[red]x AUSENTE[/red]"
        else:
            status_cell = row.status
        vals.append(status_cell)

        table.add_row(*vals)

    console.print(table)
    console.print()


def _show_comparison_summary(comp: ComparisonResult, query_names: list[str], group_result: GroupResult):
    """Display summary stats for a comparison."""
    total = comp.total_keys
    console.print(f"  [bold]Coluna: {comp.column}[/bold]")
    console.print(f"    [green]v Iguais:[/green]      {comp.equal_count}/{total}")
    if comp.normalized_count > 0:
        console.print(f"    [green]v Normalizados:[/green] {comp.normalized_count}/{total}")
    console.print(f"    [yellow]! Diferentes:[/yellow]  {comp.diff_count}/{total}")
    console.print(f"    [red]x Ausentes:[/red]    {comp.absent_count}/{total}")

    # Detail absent keys
    if comp.absent_count > 0:
        absent_keys = [str(r.key_value) for r in comp.rows if r.status == "ABSENT"]
        for r in comp.rows:
            if r.status == "ABSENT":
                missing_in = [qn for qn, v in r.values.items() if v is None]
                if missing_in:
                    console.print(f"      chave {r.key_value}: ausente em {', '.join(missing_in)}")
