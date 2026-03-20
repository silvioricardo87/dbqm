"""Collapsible sidebar navigation widget."""

from __future__ import annotations

from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


MENU_ITEMS: list[tuple[str, list[tuple[str, str, str]]]] = [
    ("CONSULTAS", [
        ("exec_query", "\U0001f50d", "Executar"),
        ("adhoc_sql", "\u2328", "SQL avulso"),
        ("config_query", "\U0001f4dd", "Gerenciar"),
    ]),
    ("GRUPOS", [
        ("exec_group", "\U0001f4ca", "Executar"),
        ("config_group", "\U0001f4c1", "Gerenciar"),
    ]),
    ("FERRAMENTAS", [
        ("extract_ddl", "\U0001f3d7", "DDL"),
        ("browse", "\U0001f5c2", "Objetos"),
        ("history", "\U0001f4dc", "Historico"),
    ]),
    ("SISTEMA", [
        ("config_conn", "\U0001f50c", "Conexoes"),
        ("portability", "\U0001f4e6", "Exportar"),
        ("settings", "\u2699", "Config"),
        ("exit", "\U0001f6aa", "Sair"),
    ]),
]


class SidebarItemSelected(Message):
    """Posted when a sidebar menu item is clicked."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__()


class SidebarItem(Static):
    """A single clickable menu item in the sidebar."""

    def __init__(self, action: str, icon: str, label: str) -> None:
        self._action = action
        self._icon = icon
        self._label = label
        super().__init__(f"{icon} {label}")
        self.add_class("sidebar-item")
        self.set_styles("height: 1;")

    def on_click(self) -> None:
        self.post_message(SidebarItemSelected(self._action))


class SidebarSectionLabel(Static):
    """A section header label in the sidebar."""

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.add_class("sidebar-section-label")


class Sidebar(Vertical):
    """Collapsible sidebar navigation docked to the left."""

    collapsed: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    Sidebar {
        dock: left;
        width: 24;
        background: $surface;
        border-right: solid $primary-background;
        padding: 1 0;
    }

    Sidebar.sidebar--collapsed {
        width: 5;
    }

    .sidebar-section-label {
        color: $text-muted;
        text-style: dim;
        padding: 1 1 0 1;
        height: auto;
    }

    Sidebar.sidebar--collapsed .sidebar-section-label {
        display: none;
    }

    .sidebar-item {
        padding: 0 1;
        height: 1;
        color: $text;
    }

    .sidebar-item:hover {
        background: $primary-background;
    }

    .sidebar-item--active {
        border-left: thick $primary;
        background: $primary-background;
        color: $text;
    }

    .sidebar-separator {
        height: 1;
    }
    """

    def compose(self):
        for idx, (section_name, items) in enumerate(MENU_ITEMS):
            if idx > 0:
                yield Static("", classes="sidebar-separator")
            yield SidebarSectionLabel(section_name)
            for action, icon, label in items:
                yield SidebarItem(action, icon, label)

    def watch_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self.add_class("sidebar--collapsed")
        else:
            self.remove_class("sidebar--collapsed")

    def toggle_collapse(self) -> None:
        """Toggle between full and collapsed sidebar."""
        self.collapsed = not self.collapsed

    def set_active(self, action: str) -> None:
        """Highlight the menu item matching the given action."""
        for item in self.query(".sidebar-item"):
            if isinstance(item, SidebarItem) and item._action == action:
                item.add_class("sidebar-item--active")
            else:
                item.remove_class("sidebar-item--active")
