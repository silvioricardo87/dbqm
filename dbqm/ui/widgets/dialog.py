"""Dialog: a camada que flutua sobre o conteudo.

Existe porque o mesmo bloco `border: thick $accent` estava copiado 29 vezes em
13 arquivos. Regra de uso: se flutua sobre o conteudo, e Dialog; se nao flutua,
e Panel.

As variantes de `largura` sao fechadas de proposito. Se um caso precisa de
algo fora delas, isso e uma variante nova que falta no sistema — nunca uma
excecao local (`dialog.styles.width = ...` depois de construir). A excecao
local e como o sistema morre: silenciosamente, um caso de cada vez, e sem
que a validacao do `__init__` veja nada, porque a escrita acontece depois
dela. `tests/ui/test_widgets.py::test_dialog_has_no_style_override_
outside_the_component` fecha essa porta.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

# "sm"/"md"/"lg" sao colunas de largura fixa (numero de celulas) — dialogos
# compactos de texto/formulario. "screen" e a excecao documentada: dialogos
# que existem para EXIBIR conteudo (tabela de resultado, texto renderizado)
# precisam preencher a maior parte da viewport, entao a unidade muda para
# porcentagem. Misturar celulas e porcentagem sem avisar seria a mesma
# mentira que um degrau de luminancia fora de ordem — por isso o comentario.
WIDTHS: dict[str, int | str] = {"sm": 50, "md": 70, "lg": 90, "screen": "90%"}
TONES: tuple[str, ...] = ("neutral", "destructive")

# Altura usada apenas pela variante "screen" — as demais ficam com o
# `height: auto; max-height: 90%` do DEFAULT_CSS, que basta para conteudo
# curto. Uma unica altura para os dois casos que hoje pedem "screen": a
# diferenca entre 80% e 85% entre eles nunca foi uma decisao, so copia.
_SCREEN_HEIGHT = "85%"


class Dialog(Vertical):
    """Chrome de uma camada flutuante: moldura, titulo e area de conteudo."""

    DEFAULT_CSS = """
    Dialog {
        width: auto;
        height: auto;
        max-height: 90%;
        background: $ds-panel;
        border: thick $ds-border-strong;
        padding: 1 2;
    }
    Dialog.-destructive { border: thick $ds-op-failure; }
    Dialog .dialog-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        title: str,
        *,
        width: str = "md",
        tone: str = "neutral",
        id: str | None = None,
    ) -> None:
        if width not in WIDTHS:
            raise ValueError(f"largura desconhecida: {width!r}; use {sorted(WIDTHS)}")
        if tone not in TONES:
            raise ValueError(f"tom desconhecido: {tone!r}; use {list(TONES)}")
        super().__init__(id=id, classes=f"-{tone}")
        self._title = title
        self.styles.width = WIDTHS[width]
        if width == "screen":
            self.styles.height = _SCREEN_HEIGHT

    def compose(self) -> ComposeResult:
        # Verificado nesta versao do Textual: o compose do proprio widget e os
        # filhos passados por `with Dialog(...)` coexistem, nesta ordem.
        yield Static(self._title, classes="dialog-title", id=f"{self.id}-title")
