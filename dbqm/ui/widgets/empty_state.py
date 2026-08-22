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
    EmptyState .empty-o-que {
        text-style: bold;
        color: $texto;
        width: 100%;
        content-align: center middle;
    }
    EmptyState .empty-porque {
        color: $texto-apoio;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        o_que: str,
        porque: str,
        acao_rotulo: str,
        acao_id: str,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._o_que = o_que
        self._porque = porque
        self._acao_rotulo = acao_rotulo
        self._acao_id = acao_id

    def compose(self) -> ComposeResult:
        yield Static(self._o_que, classes="empty-o-que")
        yield Static(self._porque, classes="empty-porque")
        yield Button(self._acao_rotulo, variant="primary", id=self._acao_id)
