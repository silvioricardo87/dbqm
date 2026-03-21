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
        ("package_editor", "\U0001f4e6", "Packages"),
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

    can_focus = False

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

    can_focus = False

    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.add_class("sidebar-section-label")


class Sidebar(Vertical):
    """Collapsible sidebar navigation docked to the left."""

    can_focus = True
    collapsed: reactive[bool] = reactive(False)
    _selected_index: reactive[int] = reactive(0)

    DEFAULT_CSS = """
    Sidebar {
        dock: left;
        width: 24;
        background: $surface;
        border-right: solid $primary-background;
        padding: 1 0;
    }

    Sidebar:focus-within {
        border-right: solid $accent;
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

    .sidebar-item--cursor {
        background: $accent 30%;
        text-style: reverse;
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

    def on_mount(self) -> None:
        """Build the list of focusable item indices after mount."""
        self._focusable_items: list[SidebarItem] = list(self.query(SidebarItem))
        if self._focusable_items:
            self._update_cursor()

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

    def _update_cursor(self) -> None:
        """Update visual cursor to match _selected_index."""
        for i, item in enumerate(self._focusable_items):
            if i == self._selected_index:
                item.add_class("sidebar-item--cursor")
            else:
                item.remove_class("sidebar-item--cursor")

    def watch__selected_index(self, value: int) -> None:
        """React to _selected_index changes."""
        if hasattr(self, '_focusable_items') and self._focusable_items:
            self._update_cursor()

    def key_up(self) -> None:
        """Move cursor up."""
        if not self._focusable_items:
            return
        self._selected_index = (self._selected_index - 1) % len(self._focusable_items)

    def key_down(self) -> None:
        """Move cursor down."""
        if not self._focusable_items:
            return
        self._selected_index = (self._selected_index + 1) % len(self._focusable_items)

    def key_enter(self) -> None:
        """Select the currently highlighted item and release focus to content."""
        if not self._focusable_items:
            return
        item = self._focusable_items[self._selected_index]
        self.post_message(SidebarItemSelected(item._action))
        # Release focus so the screen's _set_initial_focus takes over
        self.app.call_after_refresh(self._release_focus)

    def _release_focus(self) -> None:
        """Move focus away from sidebar to the content area."""
        try:
            screen_area = self.app.query_one("#screen-area")
            # Find the first focusable widget in the content area
            for widget in screen_area.query("*"):
                if widget.can_focus:
                    widget.focus()
                    return
        except Exception:
            pass

    def key_home(self) -> None:
        """Jump to first item."""
        if self._focusable_items:
            self._selected_index = 0

    def key_end(self) -> None:
        """Jump to last item."""
        if self._focusable_items:
            self._selected_index = len(self._focusable_items) - 1
