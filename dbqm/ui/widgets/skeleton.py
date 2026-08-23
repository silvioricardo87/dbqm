"""Skeleton de carregamento: a forma do conteudo que vem.

Um rodopio centralizado nao diz nada sobre o que esta chegando e deixa o
layout saltar quando o conteudo entra. O esqueleto reserva o espaco certo:
`linhas` x `colunas` de blocos, na forma da tabela que vai substitui-lo.

Fechado de proposito, no mesmo espirito de `dialog.py`/`verdict.py`: os
unicos dois graus de liberdade sao `linhas` e `colunas`, ambos inteiros —
nao ha variante de estilo para sobrescrever. Um chamador que precisar de
outra aparencia precisa de um widget novo, nunca de
`skeleton.styles.*` depois de construir; ``test_dialog_has_no_style_
override_outside_the_component`` (varredura de `.styles.(width|height) =`
em toda `dbqm/ui/`) ja fecha essa porta para qualquer widget, este
incluido.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static


class Skeleton(Vertical):
    """Placeholder com a forma de uma tabela de `linhas` x `colunas`."""

    DEFAULT_CSS = """
    Skeleton { height: auto; width: 100%; }
    Skeleton .skeleton-row { height: 1; width: 100%; }
    Skeleton .skeleton-cell {
        height: 1;
        width: 1fr;
        margin: 0 1 0 0;
        background: $ds-surface-raised;
    }
    """

    def __init__(
        self,
        rows: int = 5,
        columns: int = 4,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._rows = rows
        self._columns = columns

    def compose(self) -> ComposeResult:
        for _ in range(self._rows):
            with Horizontal(classes="skeleton-row"):
                for _ in range(self._columns):
                    yield Static("", classes="skeleton-cell")
