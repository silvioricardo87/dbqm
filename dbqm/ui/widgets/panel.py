"""Reusable bordered Panel with the title placed inside the box.

Implements design guidelines 3 (continuous border, title inside), 4
(focus-within lighting), 5 (no nested borders). Corners use `border: round`.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.scalar import Unit
from textual.widget import Widget
from textual.widgets import Label


class Panel(Vertical):
    #: Linhas que a moldura consome antes do corpo: 2 de borda (topo e
    #: base) + 1 de titulo + 1 da regua `border-bottom` do titulo.
    CROMO = 4

    DEFAULT_CSS = """
    Panel {
        border: round $borda;
        background: $panel;
        height: 1fr;
        padding: 0;
    }
    Panel:focus-within { border: round $primary; }
    Panel.accent-focus:focus-within { border: round $accent; }

    Panel > #panel-title {
        height: auto;
        width: 100%;
        color: $primary;
        text-style: bold;
        background: $surface;
        border-bottom: solid $borda;
        padding: 0 1;
    }
    Panel.accent-focus > #panel-title { color: $accent; }

    Panel > #panel-body {
        /* `1fr` e o caso comum: o painel recebe uma altura e o corpo a
           preenche. Quando o PROPRIO painel pede `height: auto` este `1fr`
           vira a mentira silenciosa descrita em `_ajustar_corpo`, e a
           classe `-conteudo` (logo abaixo) toma o lugar dele. */
        height: 1fr;
        padding: 1 1;
        /* Transbordo vertical VISIVEL: um painel mais alto que a caixa
           rola, em vez de cortar em silencio. A secao Oracle Instant
           Client das Configuracoes nascia em y=39 de um corpo que nao
           rolava — nao havia como chegar nela num terminal de 24 linhas.
           `auto` e nao `scroll` de proposito: quando o filho ocupa `1fr`
           (DataTable, OptionList) nada transborda, nenhuma barra aparece
           e nao se cria rolagem aninhada em cima da do proprio widget. */
        overflow-y: auto;
    }
    /* Ligada por `_ajustar_corpo` quando o proprio painel pede
       `height: auto`. Classe, e nao escrita direta de altura em `styles`,
       porque `dbqm/ui` tem um guarda contra esse tipo de escrita fora do
       componente (o tamanho de um `Dialog` so pode ser decidido dentro de
       `dialog.py`) — furar aquele guarda para resolver este problema seria
       trocar um silencio por outro. */
    Panel > #panel-body.-conteudo { height: auto; }
    /* guideline 5: inner widgets carry no border of their own */
    Panel #panel-body DataTable,
    Panel #panel-body OptionList,
    Panel #panel-body TextArea,
    Panel #panel-body Input,
    Panel #panel-body Select { border: none; }
    """

    def __init__(self, title: str, *, accent: bool = False, id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = title
        # NOTE: intentionally NOT named `_pending_children` — Textual's own
        # `Widget.__init__`/`Widget._compose()` already own an attribute with
        # that exact name and merge it with `compose(self)` results, mounting
        # everything as direct children of this Panel. Reusing that name here
        # would smuggle caller-yielded children in as siblings of
        # `#panel-title`/`#panel-body` instead of routing them into the body.
        self._panel_pending_children: list[Widget] = []
        if accent:
            self.add_class("accent-focus")

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="panel-title")
        yield Vertical(id="panel-body")

    def compose_add_child(self, widget: Widget) -> None:
        # `compose_add_child` runs while this Panel itself is being composed,
        # before `#panel-body` exists in the DOM — so we cannot mount into it
        # yet. Stash caller-yielded children and route them once mounted.
        self._panel_pending_children.append(widget)

    def on_mount(self) -> None:
        if self._panel_pending_children:
            body = self.query_one("#panel-body", Vertical)
            body.mount(*self._panel_pending_children)
            self._panel_pending_children = []
        self._ajustar_corpo()

    def _ajustar_corpo(self) -> None:
        """Faz `height: auto` no painel significar mesmo "do tamanho do conteudo".

        `#panel-body` nasce com `height: 1fr`. Um `1fr` dentro de um pai de
        altura automatica nao mede o conteudo: ele estica ate a altura do
        CONTAINER do painel. O efeito e que `Panel { height: auto }` nunca
        funcionou — e falhava em SILENCIO, que e o problema real. Tres
        paineis de tres linhas cada, num terminal de 24 linhas:

            Vertical height:auto -> height=6  cada, y=1 / y=8  / y=15
            Panel    height:auto -> height=24 cada, y=1 / y=24 / y=47

        As duas ultimas secoes nascem abaixo da dobra sem que nada no CSS
        pareca errado. Por isso o corpo passa a `auto` quando o painel pediu
        `auto`: a declaracao passa a fazer o que diz. Ler `self.styles.height`
        (e nao um modificador explicito tipo `Panel.-conteudo`) e o que
        mantem a regra valida para quem escreve CSS normal — ninguem precisa
        saber que existe uma regra.

        `max-height` junto com `auto` precisa da aritmetica: um corpo em
        `auto` nao ve o teto do pai, e `max-height: 100%` no corpo erraria
        por `CROMO` linhas (percentual resolve contra o pai INTEIRO, titulo
        incluido) — o corpo nasceria mais alto que a caixa e as ultimas
        linhas ficariam recortadas, fora do alcance da rolagem. Descontar
        `CROMO` deixa o corpo caber exatamente e o excesso ROLAR, visivel.
        Teto em unidade que nao seja celula nao tem essa conta: nesse caso o
        corpo fica em `1fr`, que preenche a caixa e rola — nunca corta.

        `tests/design/test_transbordo_vertical.py` renderiza os tres casos e
        falha se o acoplamento se perder. Ele e a razao de isto nao poder
        voltar a falhar calado.
        """
        altura = self.styles.height
        if altura is None or not altura.is_auto:
            return
        corpo = self.query_one("#panel-body", Vertical)
        teto = self.styles.max_height
        if teto is not None:
            if teto.unit is not Unit.CELLS:
                return
            corpo.styles.max_height = max(int(teto.value) - self.CROMO, 1)
        corpo.add_class("-conteudo")

    @property
    def corpo(self) -> Vertical:
        """O container onde o conteudo do painel vive.

        `compose_add_child` so roteia o que o chamador rende dentro do
        `with Panel(...)`. Montagem em RUNTIME (`painel.mount(...)`, como a
        barra de filtro e a lista de `query_exec`/`group_run` fazem) nao
        passa por ele e cairia como IRMA de `#panel-title`/`#panel-body`,
        fora da moldura. Quem monta depois do compose monta aqui.
        """
        return self.query_one("#panel-body", Vertical)

    def set_title(self, title: str) -> None:
        self._title = title
        self.query_one("#panel-title", Label).update(title)
