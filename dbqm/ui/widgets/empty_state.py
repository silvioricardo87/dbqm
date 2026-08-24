"""EmptyState: a primeira tela de todo usuario novo, em todo modulo.

Os quatro parametros sao obrigatorios de proposito. E o que impede repetir
"Nenhuma consulta configurada" sem oferecer a saida — o antipadrao que estava
em 22 dos 23 estados vazios do dbqm.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, Static


class EmptyState(Vertical):
    """Diz o que e aquilo, por que esta vazio, e oferece a primeira acao."""

    DEFAULT_CSS = """
    EmptyState {
        height: auto;
        width: 100%;
        padding: 2;
        content-align: center middle;
    }
    EmptyState .empty-what {
        text-style: bold;
        color: $ds-text;
        width: 100%;
        content-align: center middle;
    }
    EmptyState .empty-why {
        color: $ds-text-muted;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        what: str,
        why: str,
        action_label: str,
        action_id: str,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._what = what
        self._why = why
        self._action_label = action_label
        self._action_id = action_id

    def compose(self) -> ComposeResult:
        yield Static(self._what, classes="empty-what")
        yield Static(self._why, classes="empty-why")
        yield Button(self._action_label, variant="primary", id=self._action_id)
