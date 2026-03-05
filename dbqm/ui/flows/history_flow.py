"""Execution history browsing flow."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from dbqm.core.history import load_history, clear_history
from dbqm.ui.display import show_warning, show_success
from dbqm.ui.prompts import select, confirm, is_esc

console = Console()


def history_flow():
    """Browse execution history."""
    entries = load_history()
    if not entries:
        show_warning("Nenhum historico de execucao.")
        return

    while True:
        entries = load_history()
        if not entries:
            show_warning("Historico vazio.")
            return

        table = Table(
            title="Historico de Execucoes",
            show_lines=False,
            border_style="dim",
            title_style="bold cyan",
            header_style="bold",
            expand=True,
        )
        table.add_column("#", style="dim", width=4)
        table.add_column("Data/Hora", style="white", width=20)
        table.add_column("Tipo", width=8)
        table.add_column("Nome", style="bold white")
        table.add_column("Conexao", style="dim")
        table.add_column("Resultado", justify="center")
        table.add_column("Tempo", justify="right", width=8)

        for i, e in enumerate(entries[:50], 1):
            if e.entry_type == "group":
                tipo = "[cyan]grupo[/cyan]"
                if e.all_match is True:
                    resultado = "[green]OK[/green]"
                elif e.all_match is False:
                    resultado = "[red]DIFF[/red]"
                else:
                    resultado = "[dim]-[/dim]"
            else:
                tipo = "[white]query[/white]"
                if e.success:
                    resultado = f"[green]{e.row_count} rows[/green]"
                else:
                    resultado = "[red]ERRO[/red]"

            table.add_row(
                str(i),
                e.timestamp,
                tipo,
                e.name,
                e.connection or "-",
                resultado,
                f"{e.elapsed:.1f}s",
            )

        console.print()
        console.print(table)
        console.print()

        action = select(
            message="Acao:",
            choices=[
                {"name": "🔍  Ver detalhes", "value": "detail"},
                {"name": "🗑️   Limpar historico", "value": "clear"},
                {"name": "↩️   Voltar", "value": "back"},
            ],
        )
        if is_esc(action) or action == "back":
            return
        elif action == "clear":
            do_clear = confirm(message="Limpar todo o historico?", default=False)
            if not is_esc(do_clear) and do_clear:
                clear_history()
                show_success("Historico limpo!")
                return
        elif action == "detail":
            _show_detail(entries)


def _show_detail(entries):
    """Show details of a history entry."""
    choices = [
        {"name": f"{e.timestamp} | {e.entry_type} | {e.name}", "value": i}
        for i, e in enumerate(entries[:50])
    ]
    idx = select(message="Selecione:", choices=choices)
    if is_esc(idx):
        return

    e = entries[idx]
    console.print()
    console.print(f"  [bold]Tipo:[/bold] {e.entry_type}")
    console.print(f"  [bold]Nome:[/bold] {e.name}")
    console.print(f"  [bold]Data:[/bold] {e.timestamp}")
    if e.connection:
        console.print(f"  [bold]Conexao:[/bold] {e.connection}")
    if e.params:
        for k, v in e.params.items():
            console.print(f"  [bold]{k}:[/bold] {v}")
    console.print(f"  [bold]Tempo:[/bold] {e.elapsed:.2f}s")
    if e.entry_type == "query":
        console.print(f"  [bold]Registros:[/bold] {e.row_count}")
        console.print(f"  [bold]Sucesso:[/bold] {'Sim' if e.success else 'Nao'}")
        if e.error:
            console.print(f"  [bold]Erro:[/bold] {e.error}")
    elif e.entry_type == "group":
        if e.all_match is not None:
            status = "[green]CONSISTENTE[/green]" if e.all_match else "[red]DIVERGENTE[/red]"
            console.print(f"  [bold]Resultado:[/bold] {status}")
        if e.summary:
            console.print(f"  [bold]Resumo:[/bold] {e.summary}")
    console.print()
