"""Help overlay showing keyboard shortcuts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


HELP_TEXT = """\
[bold]Atalhos de Teclado[/bold]

[bold cyan]Geral[/bold cyan]
  Ctrl+B    Toggle sidebar
  Ctrl+Q    Sair
  ESC       Voltar
  /         Buscar/filtrar
  ?         Esta ajuda

[bold cyan]Resultado de consulta[/bold cyan]
  V         Visualizacao vertical
  E         Exportar
  R         Reexecutar

[bold cyan]Resultado de grupo[/bold cyan]
  F         Flat/Pivoted
  S         Filtrar status
  E         Exportar
  H         Relatorio HTML
  I         Ver individual
  R         Reexecutar

[dim]Pressione ESC, Enter ou ? para fechar[/dim]
"""


class HelpModal(ModalScreen[None]):
    """Displays keyboard shortcuts in a modal overlay."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }

    HelpModal #help-dialog {
        width: 55;
        max-height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_help", "Fechar", show=False),
        Binding("enter", "dismiss_help", "Fechar", show=False),
        Binding("question_mark", "dismiss_help", "Fechar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="help-dialog"):
            yield Static(HELP_TEXT, markup=True)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
