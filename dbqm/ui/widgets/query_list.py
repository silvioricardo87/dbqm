"""QueryList widget — displays queries as selectable items in a ListView."""

from __future__ import annotations

from typing import Any

from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Input, ListView, ListItem, Static


class QuerySelected(Message):
    """Posted when a query is selected from the list."""

    def __init__(self, query_name: str) -> None:
        self.query_name = query_name
        super().__init__()


def _attr(obj: Any, key: str, default: Any = "") -> Any:
    """Get attribute from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class _QueryListItem(ListItem):
    """A single query entry inside the ListView."""

    DEFAULT_CSS = """
    _QueryListItem {
        height: 1;
        padding: 0 1;
    }
    _QueryListItem Horizontal {
        height: 1;
        width: 1fr;
    }
    _QueryListItem .ql-star {
        width: 2;
    }
    _QueryListItem .ql-name {
        width: 20;
        min-width: 12;
        text-style: bold;
    }
    _QueryListItem .ql-desc {
        width: 1fr;
        color: $text-muted;
    }
    _QueryListItem .ql-conn {
        width: 16;
        min-width: 10;
        text-align: right;
        color: $warning;
    }
    _QueryListItem .ql-table {
        width: 16;
        min-width: 10;
        text-align: right;
        color: $text-muted;
    }
    """

    def __init__(self, query: Any) -> None:
        self.query_data = query
        self.query_name: str = _attr(query, "name", "")
        super().__init__()

    def compose(self):
        is_fav = _attr(self.query_data, "is_favorite", False)
        star = "[yellow]★[/]" if is_fav else "[dim]☆[/]"
        name = _attr(self.query_data, "name", "")
        desc = _attr(self.query_data, "description", "")
        if len(desc) > 40:
            desc = desc[:37] + "..."
        conn = _attr(self.query_data, "connection", "")
        table = _attr(self.query_data, "table", "")

        with Horizontal():
            yield Static(star, classes="ql-star", markup=True)
            yield Static(name, classes="ql-name")
            yield Static(desc or "", classes="ql-desc")
            yield Static(conn, classes="ql-conn")
            yield Static(table, classes="ql-table")


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
    QueryListWidget ListView {
        height: 1fr;
    }
    QueryListWidget ListView > ListItem.--highlight {
        background: $primary 30%;
    }
    QueryListWidget ListView:focus > ListItem.--highlight {
        background: $primary 50%;
    }
    QueryListWidget ListView > ListItem.--highlight .ql-name {
        color: $text;
        text-style: bold;
    }
    QueryListWidget ListView > ListItem.--highlight .ql-conn {
        color: $warning-lighten-2;
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
        """Delegate focus to the internal ListView."""
        try:
            self.query_one("#ql-listview", ListView).focus(scroll_visible)
        except Exception:
            super().focus(scroll_visible)

    def compose(self):
        with Horizontal(id="ql-search"):
            yield Input(placeholder="Filtrar consultas...", id="ql-search-input")
        yield ListView(id="ql-listview")

    def on_mount(self) -> None:
        self._composed = True
        if self._all_queries:
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
        listview = self.query_one("#ql-listview", ListView)
        listview.clear()
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
            listview.append(ListItem(Static("[dim]Nenhuma consulta configurada[/]", markup=True)))
            return
        for q in sorted_queries:
            listview.append(_QueryListItem(q))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """When an item is selected, post QuerySelected if it's a real query item."""
        item = event.item
        if isinstance(item, _QueryListItem):
            self.post_message(QuerySelected(item.query_name))

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

    def key_escape(self) -> None:
        """Dismiss search on ESC if visible."""
        search_bar = self.query_one("#ql-search", Horizontal)
        if search_bar.has_class("visible"):
            self._dismiss_search()
