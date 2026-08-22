"""Esqueleto de carregamento: a forma do conteudo que vem.

Um rodopio centralizado nao diz nada sobre o que esta chegando e deixa o
layout saltar quando o conteudo entra. O esqueleto reserva o espaco certo:
`linhas` x `colunas` de blocos, na forma da tabela que vai substitui-lo.

Fechado de proposito, no mesmo espirito de `dialog.py`/`veredito.py`: os
unicos dois graus de liberdade sao `linhas` e `colunas`, ambos inteiros —
nao ha variante de estilo para sobrescrever. Um chamador que precisar de
outra aparencia precisa de um widget novo, nunca de
`esqueleto.styles.*` depois de construir; ``test_dialog_nao_tem_override_
de_estilo_fora_do_componente`` (varredura de `.styles.(width|height) =`
em toda `dbqm/ui/`) ja fecha essa porta para qualquer widget, este
incluido.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static


class Esqueleto(Vertical):
    """Placeholder com a forma de uma tabela de `linhas` x `colunas`."""

    DEFAULT_CSS = """
    Esqueleto { height: auto; width: 100%; }
    Esqueleto .esqueleto-linha { height: 1; width: 100%; }
    Esqueleto .esqueleto-celula {
        height: 1;
        width: 1fr;
        margin: 0 1 0 0;
        background: $superficie-elevada;
    }
    """

    def __init__(
        self,
        linhas: int = 5,
        colunas: int = 4,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._linhas = linhas
        self._colunas = colunas

    def compose(self) -> ComposeResult:
        for _ in range(self._linhas):
            with Horizontal(classes="esqueleto-linha"):
                for _ in range(self._colunas):
                    yield Static("", classes="esqueleto-celula")
