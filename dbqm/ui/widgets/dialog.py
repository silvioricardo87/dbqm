"""Dialog: a camada que flutua sobre o conteudo.

Existe porque o mesmo bloco `border: thick $accent` estava copiado 29 vezes em
13 arquivos. Regra de uso: se flutua sobre o conteudo, e Dialog; se nao flutua,
e Panel.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

LARGURAS: dict[str, int] = {"sm": 50, "md": 70, "lg": 90}
TONS: tuple[str, ...] = ("neutro", "destrutivo")


class Dialog(Vertical):
    """Chrome de uma camada flutuante: moldura, titulo e area de conteudo."""

    DEFAULT_CSS = """
    Dialog {
        width: auto;
        height: auto;
        max-height: 90%;
        background: $painel;
        border: thick $borda-forte;
        padding: 1 2;
    }
    Dialog.-destrutivo { border: thick $op-falha; }
    Dialog .dialog-titulo {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        titulo: str,
        *,
        largura: str = "md",
        tom: str = "neutro",
        id: str | None = None,
    ) -> None:
        if largura not in LARGURAS:
            raise ValueError(f"largura desconhecida: {largura!r}; use {sorted(LARGURAS)}")
        if tom not in TONS:
            raise ValueError(f"tom desconhecido: {tom!r}; use {list(TONS)}")
        super().__init__(id=id, classes=f"-{tom}")
        self._titulo = titulo
        self.styles.width = LARGURAS[largura]

    def compose(self) -> ComposeResult:
        # Verificado nesta versao do Textual: o compose do proprio widget e os
        # filhos passados por `with Dialog(...)` coexistem, nesta ordem.
        yield Static(self._titulo, classes="dialog-titulo", id=f"{self.id}-titulo")
