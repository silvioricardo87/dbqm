"""Progress indicator widget for long-running operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import LoadingIndicator, Static


class ProgressIndicator(Vertical, can_focus=False):
    """A compact progress indicator with a message and loading animation.

    Hidden by default. Call ``start(message)`` to show it and ``stop()`` to
    hide it again.

    EXCECAO DELIBERADA a "toda tela e feita de paineis; nada fica solto no
    fundo" (§4 da gramatica de layout). As sete telas que o usam rendem
    `ProgressIndicator()` SOLTO, irmao dos paineis, e nao dentro de um. Duas
    razoes, nesta ordem:

    1. Ele nao e uma secao — e o estado da tela INTEIRA enquanto uma
       operacao remota corre. Emoldura-lo criaria um painel que aparece e
       some, e a moldura passaria a significar duas coisas diferentes.
    2. Emoldurado, ele herdaria a visibilidade do painel que o hospedasse
       — e as telas que o usam trocam de fase apagando paineis. Em
       `exec_routine` o indicador acende com `#er-select-phase` na tela e
       so apaga quando `_show_objects` esconde essa fase: dentro dela, o
       unico sinal de que a chamada remota esta rodando sumiria junto com
       ela.

    A mesma isencao vale para `#pe-empty` (o texto de "carregando/cancelado"
    do editor de packages), pelo motivo (1): e o estado da tela, nao uma
    secao dela.
    """

    DEFAULT_CSS = """
    ProgressIndicator {
        display: none;
        height: auto;
        max-height: 3;
        padding: 0 1;
    }

    ProgressIndicator Static {
        height: 1;
        content-align: center middle;
        text-align: center;
    }

    ProgressIndicator LoadingIndicator {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="progress-message")
        yield LoadingIndicator()

    def start(self, message: str) -> None:
        """Show the indicator with *message*."""
        self.query_one("#progress-message", Static).update(message)
        self.display = True

    def stop(self) -> None:
        """Hide the indicator."""
        self.display = False

    def update_message(self, message: str) -> None:
        """Update the displayed message while the indicator is visible."""
        self.query_one("#progress-message", Static).update(message)
