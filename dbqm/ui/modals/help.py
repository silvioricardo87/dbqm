"""Help overlay showing keyboard shortcuts."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Static

from dbqm.ui.widgets.dialog import Dialog


HELP_TEXT = """\
[bold $ds-text-strong]Geral[/]
  Ctrl+B    Toggle sidebar
  Ctrl+Q    Sair
  ESC       Voltar
  /         Buscar/filtrar
  ?         Esta ajuda

[bold $ds-text-strong]Resultado de consulta[/]
  V         Visualizacao vertical
  E         Exportar
  R         Reexecutar

[bold $ds-text-strong]Resultado de grupo[/]
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
        overflow-y: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss_help", "Fechar", show=False),
        Binding("enter", "dismiss_help", "Fechar", show=False),
        Binding("question_mark", "dismiss_help", "Fechar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Dialog("Atalhos de Teclado", width="sm", id="help-dialog"):
            yield Static(HELP_TEXT, markup=True)

    def action_dismiss_help(self) -> None:
        self.dismiss(None)
