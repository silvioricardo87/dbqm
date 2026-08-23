"""QueryList widget — displays queries as selectable items in an OptionList."""

from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Input, OptionList, Static

from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.lista_hierarquica import OpcaoNomeada, item_hierarquico


class QuerySelected(Message):
    """Posted when a query is selected from the list."""

    def __init__(self, query_name: str) -> None:
        self.query_name = query_name
        super().__init__()


class ClearFiltersRequested(Message):
    """Posted when the user asks, from the filtered-to-nothing EmptyState,
    to clear whatever is hiding the queries. The widget already clears its
    own inline search box; folder/connection/text filters above it belong
    to the host screen, which is the only side that knows how to reset
    them."""


def _attr(obj: Any, key: str, default: Any = "") -> Any:
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _query_option(query: Any) -> OpcaoNomeada:
    """Monta a `OpcaoNomeada` de uma consulta pra dentro do `OptionList`.

    Renders com a hierarquia de linhas do layout grammar
    (`item_hierarquico`): nome sozinho na identidade, conexao+tabela como
    desambiguacao (o que separa duas consultas de nome parecido), descricao
    como contexto opcional. O nome da consulta viaja no atributo `nome` da
    opcao, e nao no `id` — ver `OpcaoNomeada`: duas consultas de mesmo nome
    sao dado ambiguo, mas dado ambiguo nao pode derrubar a tela.
    """
    is_fav = _attr(query, "is_favorite", False)
    star = Content.assemble(
        ("★ " if is_fav else "☆ ", "$identidade" if is_fav else "$texto-desabilitado")
    )

    name = _attr(query, "name", "")
    desc = _attr(query, "description", "")
    conn = _attr(query, "connection", "")
    table = _attr(query, "table", "")

    # Desambiguacao: conexao e tabela sao o que distingue duas consultas
    # de nome parecido — mesmo par (alvo, conexao) que o docstring de
    # item_hierarquico usa como exemplo.
    desambiguacao = f"{conn} - {table}" if conn and table else (conn or table)
    # Contexto: descricao, sem corte artificial — a hierarquia (linha
    # propria, recuada, em $texto-desabilitado) e o que a torna legivel,
    # nao um limite de caracteres. Colapsa quebras de linha internas
    # para nao estourar a gramatica de uma linha por papel.
    contexto = " ".join(desc.split())

    conteudo = star + item_hierarquico(name, desambiguacao, contexto)
    return OpcaoNomeada(conteudo, name)


class QueryListWidget(Vertical, can_focus=False):
    """Displays a list of queries with sorting, filtering, and text search."""

    DEFAULT_CSS = """
    QueryListWidget {
        height: 1fr;
    }
    QueryListWidget #ql-search {
        display: none;
        height: auto;
        margin: 0 0 1 0;
    }
    QueryListWidget #ql-search Input {
        width: 1fr;
    }
    QueryListWidget #ql-search.visible {
        display: block;
    }
    QueryListWidget OptionList {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("slash", "start_search", "Buscar", show=False),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._all_queries: list[Any] = []
        self._current_folder: str | None = None
        self._search_text: str = ""
        self._composed = False

    def focus(self, scroll_visible: bool = True) -> None:
        """Delegate focus to the internal OptionList."""
        try:
            self.query_one("#ql-listview", OptionList).focus(scroll_visible)
        except Exception:
            super().focus(scroll_visible)

    def compose(self):
        with Horizontal(id="ql-search"):
            yield Input(placeholder="Filtrar consultas...", id="ql-search-input")
        yield EmptyState(
            o_que="Consultas",
            porque="Os filtros aplicados escondem as consultas que existem",
            acao_rotulo="Limpar filtros",
            acao_id="limpar-filtros-consultas",
            id="ql-filter-empty",
        )
        yield OptionList(id="ql-listview")

    def on_mount(self) -> None:
        self._composed = True
        # Always sync visibility, even with zero queries loaded so far —
        # ``_refresh_items`` is what decides EmptyState vs OptionList, and
        # skipping it here left both in their compose-time default state.
        self._refresh_items()

    def load_queries(self, queries: list[Any]) -> None:
        """Populate the list with queries. Sorts favorites first, then by name."""
        self._all_queries = list(queries)
        if self._composed:
            self._refresh_items()

    def filter_folder(self, folder: str | None) -> None:
        """Filter items by folder. None shows all."""
        self._current_folder = folder
        if self._composed:
            self._refresh_items()

    def _sorted(self, queries: list[Any]) -> list[Any]:
        return sorted(
            queries,
            key=lambda q: (not _attr(q, "is_favorite", False), _attr(q, "name", "").lower()),
        )

    def _refresh_items(self) -> None:
        option_list = self.query_one("#ql-listview", OptionList)
        empty = self.query_one("#ql-filter-empty", EmptyState)
        option_list.clear_options()
        filtered = self._all_queries
        if self._current_folder is not None:
            filtered = [q for q in filtered if _attr(q, "folder", "") == self._current_folder]

        if self._search_text:
            term = self._search_text.lower()
            filtered = [
                q for q in filtered
                if term in _attr(q, "name", "").lower()
                or term in _attr(q, "description", "").lower()
            ]

        sorted_queries = self._sorted(filtered)
        if not sorted_queries:
            # Um `Option` nao hospeda widget nenhum, entao o caso vazio e um
            # EmptyState ao lado do OptionList (que se esconde), nunca uma
            # linha falsa dentro dele.
            empty.display = True
            option_list.display = False
            return
        empty.display = False
        option_list.display = True
        for q in sorted_queries:
            option_list.add_option(_query_option(q))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """When an item is selected, post QuerySelected if it's a real query item."""
        if event.option_list.id != "ql-listview":
            return
        if not isinstance(event.option, OpcaoNomeada):
            return
        # Nome vazio tambem e postado: a tela responde "Consulta '' nao
        # encontrada", que e informacao. Engolir a selecao aqui daria uma
        # linha visivel que nao faz nada ao ser escolhida.
        self.post_message(QuerySelected(event.option.nome))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "limpar-filtros-consultas":
            # Clear what the widget owns itself (its own inline search);
            # folder/connection/text filters living in the host screen are
            # its own to reset, hence the message.
            self._search_text = ""
            try:
                search_input = self.query_one("#ql-search-input", Input)
                search_input.value = ""
                self.query_one("#ql-search", Horizontal).remove_class("visible")
            except Exception:
                pass
            self.post_message(ClearFiltersRequested())
            self._refresh_items()

    def action_start_search(self) -> None:
        """Show the search input."""
        search_bar = self.query_one("#ql-search", Horizontal)
        search_bar.add_class("visible")
        search_input = self.query_one("#ql-search-input", Input)
        search_input.value = ""
        search_input.focus()

    def _dismiss_search(self) -> None:
        """Hide the search input and reset filter."""
        search_bar = self.query_one("#ql-search", Horizontal)
        search_bar.remove_class("visible")
        self._search_text = ""
        self._refresh_items()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter as user types."""
        if event.input.id == "ql-search-input":
            self._search_text = event.value
            self._refresh_items()

    def on_key(self, event) -> None:
        """Dismiss the search on ESC when it is open.

        Uses on_key (not key_escape) so the event can be stopped only when the
        search bar is actually visible. Otherwise ESC must bubble up to the
        app-level go-back binding — swallowing it here would trap the user in
        the screen, and a bare key_escape would let ESC both close the search
        AND clear the whole screen.
        """
        if event.key != "escape":
            return
        search_bar = self.query_one("#ql-search", Horizontal)
        if search_bar.has_class("visible"):
            self._dismiss_search()
            self.query_one("#ql-listview", OptionList).focus()
            event.stop()
            event.prevent_default()
