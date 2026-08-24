"""QueryList widget — displays queries as selectable items in an OptionList."""

from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.content import Content
from textual.message import Message
from textual.widgets import Button, Input, OptionList, Static

from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.hierarchical_list import (
    NamedOption,
    hierarchical_item,
    wrap_width,
    wrap_lines,
)


# Width of the panel that hosts this list (`#selection-phase`, in
# `dbqm/ui/screens/query_exec.py`). It lives here, and not there, because
# the one that needs it in order to wrap the text is this module; the
# screen imports this constant for its own CSS, so that the declared
# width and the width assumed when wrapping are literally the same number.
#
# THE PRICE of this constant, written down because it is a choice and not
# a pure gain: the Consultas panel STOPS BEING ELASTIC. It used to grow
# with the terminal (116 columns in a 120-column terminal); now it stops
# at 76 and whatever is left on the right stays empty. This was the
# trade-off accepted to cure the defect that opened this phase — a query
# description overflowed the width, Textual wrapped the line at render
# time, and the continuation landed in column 0, the SAME column as the
# identity of the next query; the eye could not tell a continuation from
# a new entry. A guaranteed indent requires breaking on `\n` before the
# render (see `hierarchical_item`), and breaking on `\n` requires knowing
# the width before the render.
#
# 76 is the width the panel already had in the narrowest terminal the
# product supports (80 columns minus the screen's `margin: 1 2 0 2`, 4
# columns). Chosen that way on purpose: at 80x24 nothing moves, and only
# wider terminals pay the price.
LIST_PANEL_WIDTH = 76

# Text columns left over inside that panel — single derivation, shared
# with the Conexoes list (whose panel is 42). See `wrap_width` for the
# individual parts and for the scrollbar trap.
_TEXT_WIDTH = wrap_width(LIST_PANEL_WIDTH)


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


def _query_option(query: Any) -> NamedOption:
    """Builds the `NamedOption` of a query to go into the `OptionList`.

    Renders with the line hierarchy of the layout grammar
    (`hierarchical_item`): name alone as the identity, connection+table as
    disambiguation (what separates two queries with similar names),
    description as optional context. The query name travels in the
    option's `name` attribute, not in its `id` — see `NamedOption`: two
    queries with the same name are ambiguous data, but ambiguous data must
    not be able to bring the screen down.
    """
    is_fav = _attr(query, "is_favorite", False)
    star = Content.assemble(
        ("★ " if is_fav else "☆ ", "$ds-identity" if is_fav else "$ds-text-disabled")
    )

    name = _attr(query, "name", "")
    desc = _attr(query, "description", "")
    conn = _attr(query, "connection", "")
    table = _attr(query, "table", "")

    # Disambiguation: connection and table are what distinguishes two
    # queries with similar names — the same (target, connection) pair that
    # the docstring of hierarchical_item uses as its example.
    alvo = f"{conn} - {table}" if conn and table else (conn or table)
    # Context: description, with no artificial truncation — the hierarchy
    # (its own line, indented, in $ds-text-disabled) is what makes it
    # readable, not a character limit. What happens here is WRAPPING, not
    # truncation: no character is lost, it only gains a `\n` every
    # `_TEXT_WIDTH` columns.
    #
    # The wrapping is the fix. Without it, `hierarchical_item` received the
    # description as ONE long line, Textual wrapped it at render time and
    # the continuation came out in column 0 — glued, to the eye, to the
    # identity of the next query. Both fields go through here because both
    # are free-length user text: a long connection name and a long table
    # overflow just like the description does.
    desambiguacao = wrap_lines(alvo, _TEXT_WIDTH)
    contexto = wrap_lines(desc, _TEXT_WIDTH)

    conteudo = star + hierarchical_item(name, desambiguacao, contexto)
    return NamedOption(conteudo, name)


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
            what="Consultas",
            why="Os filtros aplicados escondem as consultas que existem",
            action_label="Limpar filtros",
            action_id="limpar-filtros-consultas",
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
            # An `Option` hosts no widget at all, so the empty case is an
            # EmptyState next to the OptionList (which hides itself), never
            # a fake row inside it.
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
        if not isinstance(event.option, NamedOption):
            return
        # An empty name is posted too: the screen replies "Consulta '' nao
        # encontrada", which is information. Swallowing the selection here
        # would give a visible row that does nothing when chosen.
        self.post_message(QuerySelected(event.option.name))

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
