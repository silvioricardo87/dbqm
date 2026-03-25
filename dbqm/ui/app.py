"""Main Textual application for DB Query Manager."""
from __future__ import annotations

import traceback

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Static

from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT
from dbqm.ui.widgets.sidebar import Sidebar, SidebarItemSelected
from dbqm.ui.widgets.breadcrumb import Breadcrumb
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.ui.widgets.action_bar import ActionBar, ActionSelected


# Map sidebar actions to breadcrumb labels
ACTION_LABELS: dict[str, str] = {
    "exec_query": "Executar Consulta",
    "adhoc_sql": "SQL Avulso",
    "config_query": "Gerenciar Consultas",
    "exec_group": "Executar Grupo",
    "config_group": "Gerenciar Grupos",
    "extract_ddl": "DDL",
    "package_editor": "Packages",
    "browse": "Objetos",
    "history": "Histórico",
    "config_conn": "Conexões",
    "settings": "Configurações",
}


class DBQMApp(App):
    """DB Query Manager — main application."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from dbqm._version import __version__
        self.title = f"DB Query Manager v{__version__}"

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "go_back", "Back"),
        Binding("question_mark", "show_help", "Ajuda", show=False),
        Binding("slash", "search", "Buscar", show=False),
        # Action bar shortcut keys — bound at app level to guarantee they work
        # regardless of which widget has focus. The action_shortcut handler
        # checks if the key matches a current action bar entry.
        Binding("n", "shortcut('n')", "", show=False, priority=True),
        Binding("t", "shortcut('t')", "", show=False, priority=True),
        Binding("e", "shortcut('e')", "", show=False, priority=True),
        Binding("r", "shortcut('r')", "", show=False, priority=True),
        Binding("d", "shortcut('d')", "", show=False, priority=True),
        Binding("v", "shortcut('v')", "", show=False, priority=True),
        Binding("f", "shortcut('f')", "", show=False, priority=True),
        Binding("s", "shortcut('s')", "", show=False, priority=True),
        Binding("h", "shortcut('h')", "", show=False, priority=True),
        Binding("i", "shortcut('i')", "", show=False, priority=True),
        Binding("p", "shortcut('p')", "", show=False, priority=True),
        Binding("c", "shortcut('c')", "", show=False, priority=True),
        Binding("b", "shortcut('b')", "", show=False, priority=True),
        Binding("x", "shortcut('x')", "", show=False, priority=True),
        Binding("q", "shortcut('q')", "", show=False, priority=True),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield Sidebar()
            with Vertical(id="content"):
                yield Breadcrumb()
                yield Container(id="screen-area")
                yield ActionBar()
        yield StatusBar()

    def on_mount(self) -> None:
        """Load settings, register themes, and set initial state."""
        from dbqm.models.settings import load_settings
        from dbqm.models.connection import load_connections
        from dbqm.models.query import load_queries
        from dbqm.models.group import load_groups

        settings = load_settings()

        self.register_theme(GITHUB_DARK)
        self.register_theme(GITHUB_LIGHT)
        self.theme = settings.theme

        connections = load_connections()
        queries = load_queries()
        groups = load_groups()

        status_bar = self.query_one(StatusBar)
        status_bar.update_counts(
            queries=len(queries),
            connections=len(connections),
            groups=len(groups),
        )

        # First-run: no connections configured
        if not connections:
            screen_area = self.query_one("#screen-area", Container)
            screen_area.mount(
                Static(
                    "[bold]Bem-vindo ao DB Query Manager![/bold]\n\n"
                    "Nenhuma conexão configurada.\n"
                    "Use o menu [bold]Conexões[/bold] para começar.",
                    id="welcome-message",
                )
            )

    def on_key(self, event) -> None:
        """Use arrow keys to navigate between widgets in content area.

        DataTable, ListView, TextArea, and Sidebar handle arrows internally.
        For other widgets (Button, Switch, Input, Select), arrows move focus.
        """
        if event.key not in ("up", "down"):
            return

        from textual.widgets import DataTable, ListView, TextArea, OptionList
        from dbqm.ui.widgets.sidebar import Sidebar

        focused = self.focused
        if focused is None:
            return

        # Check the focused widget AND its ancestors for types that use arrows
        widget_chain = [focused] + list(focused.ancestors)
        for w in widget_chain:
            if isinstance(w, (DataTable, ListView, TextArea, OptionList, Sidebar)):
                return

        # Navigate within the content section only
        self._focus_within_section(forward=(event.key == "down"))
        event.prevent_default()
        event.stop()

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        """Disable bindings contextually based on focused widget."""
        if action == "shortcut":
            from textual.widgets import Input, TextArea
            focused = self.focused
            if isinstance(focused, (Input, TextArea)):
                return False
            try:
                action_bar = self.query_one(ActionBar)
            except Exception:
                return False
            key = parameters[0] if parameters else ""
            for act in action_bar._actions:
                if act.key and act.key.lower() == key.lower():
                    return True
            return False

        return True

    def _focus_within_section(self, forward: bool) -> None:
        """Navigate focus only within the current section (sidebar or content area)."""
        focused = self.focused
        if focused is None:
            return

        try:
            sidebar = self.query_one(Sidebar)
            content = self.query_one("#content", Vertical)
        except Exception:
            return

        # Check if focused widget is inside sidebar
        in_sidebar = focused is sidebar or sidebar in focused.ancestors
        if in_sidebar:
            return

        # Get all focusable widgets inside the content area only
        # Exclude pure layout containers that shouldn't receive focus
        from textual.widgets import Select
        focusable = []
        for w in content.query("*"):
            if not w.can_focus or not w.display:
                continue
            # Include interactive widgets: Select, Button, Switch, Input, etc.
            # Exclude layout containers (Vertical, Horizontal, Container, ScrollView)
            # Select inherits from Vertical, so check it explicitly first
            if isinstance(w, Select):
                focusable.append(w)
            elif w.__class__.__name__ in (
                "Vertical", "Horizontal", "Container",
                "VerticalScroll", "HorizontalScroll",
                "NavVerticalScroll", "SettingsScreen",
            ):
                continue
            else:
                focusable.append(w)

        if not focusable:
            return

        # Find current index — focused might be a child of a focusable widget
        # (e.g. SelectCurrent inside Select), so check ancestors too
        current_idx = -1
        for i, w in enumerate(focusable):
            if w is focused or w in focused.ancestors:
                current_idx = i
                break

        if current_idx < 0:
            # Not found — focus first or last
            focusable[0 if forward else -1].focus()
            return

        if forward:
            next_idx = min(current_idx + 1, len(focusable) - 1)
        else:
            next_idx = max(current_idx - 1, 0)

        focusable[next_idx].focus()

    def action_shortcut(self, key: str) -> None:
        """Handle action bar shortcut keys (N, T, E, R, etc.)."""
        try:
            action_bar = self.query_one(ActionBar)
        except Exception:
            return

        for action in action_bar._actions:
            if action.key and action.key.lower() == key.lower():
                # Post to the active screen widget so it receives the message
                screen_area = self.query_one("#screen-area", Container)
                children = list(screen_area.children)
                if children:
                    children[0].post_message(ActionSelected(action.action_id))
                else:
                    action_bar.post_message(ActionSelected(action.action_id))
                return

    def on_action_selected(self, message: ActionSelected) -> None:
        """Forward ActionSelected from action bar clicks to the active screen.

        This is only needed for CLICK-based actions on the ActionBar markup.
        Shortcut-based actions already post directly to the screen widget.
        """
        # Only forward if this came from the ActionBar (bubbled up),
        # not from a screen (would cause infinite loop)
        if isinstance(message._sender, ActionBar):
            screen_area = self.query_one("#screen-area", Container)
            children = list(screen_area.children)
            if children:
                children[0].post_message(ActionSelected(message.action_id))
            message.stop()

    def on_sidebar_item_selected(self, message: SidebarItemSelected) -> None:
        """Handle sidebar navigation."""
        action = message.action

        if action == "exit":
            self.exit()
            return

        # Update sidebar active state
        self.query_one(Sidebar).set_active(action)

        # Update breadcrumb
        label = ACTION_LABELS.get(action, action)
        # System items get "Sistema" as parent breadcrumb
        system_actions = {"config_conn", "settings"}
        if action in system_actions:
            self.query_one(Breadcrumb).set_path(["Sistema", label])
        elif action == "config_query":
            self.query_one(Breadcrumb).set_path(["Consultas", "Gerenciar"])
        elif action == "config_group":
            self.query_one(Breadcrumb).set_path(["Grupos", "Gerenciar"])
        else:
            self.query_one(Breadcrumb).set_path(["Início", label])

        # Load appropriate screen into the content area
        screen_area = self.query_one("#screen-area", Container)
        screen_area.remove_children()

        screen_widget = None
        if action == "exec_query":
            from dbqm.ui.screens.query_exec import QueryExecScreen
            screen_widget = QueryExecScreen(id="query-exec-screen")
        elif action == "exec_group":
            from dbqm.ui.screens.group_exec import GroupExecScreen
            self.query_one(Breadcrumb).set_path(["Grupos", "Executar"])
            screen_widget = GroupExecScreen(id="group-exec-screen")
        elif action == "config_query":
            from dbqm.ui.screens.query_manage import QueryManageScreen
            screen_widget = QueryManageScreen(id="query-manage-screen")
        elif action == "config_group":
            from dbqm.ui.screens.group_manage import GroupManageScreen
            screen_widget = GroupManageScreen(id="group-manage-screen")
        elif action == "adhoc_sql":
            from dbqm.ui.screens.adhoc import AdhocScreen
            self.query_one(Breadcrumb).set_path(["Consultas", "SQL avulso"])
            screen_widget = AdhocScreen(id="adhoc-screen")
        elif action == "extract_ddl":
            from dbqm.ui.screens.ddl import DDLScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "DDL"])
            screen_widget = DDLScreen(id="ddl-screen")
        elif action == "package_editor":
            from dbqm.ui.screens.package_editor import PackageEditorScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "Packages"])
            screen_widget = PackageEditorScreen(id="package-editor-screen")
        elif action == "browse":
            from dbqm.ui.screens.browser import BrowserScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "Objetos"])
            screen_widget = BrowserScreen(id="browser-screen")
        elif action == "history":
            from dbqm.ui.screens.history import HistoryScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "Historico"])
            screen_widget = HistoryScreen(id="history-screen")
        elif action == "config_conn":
            from dbqm.ui.screens.connections import ConnectionsScreen
            screen_widget = ConnectionsScreen(id="connections-screen")
        elif action == "settings":
            from dbqm.ui.screens.settings import SettingsScreen
            self.query_one(Breadcrumb).set_path(["Sistema", "Config"])
            screen_widget = SettingsScreen(id="settings-screen")
        else:
            screen_widget = Static(f"[dim]{label}[/dim] (em construção)", id="placeholder")

        if screen_widget is not None:
            screen_area.mount(screen_widget)
            self.call_after_refresh(lambda: self._focus_screen_widget(screen_widget))

    def _focus_screen_widget(self, screen_widget) -> None:
        """Set focus to the first interactive widget within a screen."""
        try:
            # Find the first focusable child widget in the screen
            for widget in screen_widget.query("*"):
                if widget.can_focus:
                    widget.focus()
                    return
            # Fallback: focus the screen container itself
            screen_widget.focus()
        except Exception:
            pass

    def _handle_exception(self, error: Exception) -> None:
        """Global error handler — show error modal instead of crashing."""
        from dbqm.ui.modals.error import ErrorModal
        tb = traceback.format_exception(type(error), error, error.__traceback__)
        detail = "".join(tb)
        # Escape Rich markup in the traceback
        detail = detail.replace("[", "\\[")
        title = f"Erro: {type(error).__name__}"
        try:
            self.push_screen(ErrorModal(title, detail))
        except Exception:
            # Last resort: use notification
            self.notify(f"{title}: {error}", severity="error", timeout=10)
        return  # Don't re-raise — app stays alive

    def on_worker_state_changed(self, event) -> None:
        """Catch worker thread errors and show them in a modal."""
        from textual.worker import WorkerState
        if event.state == WorkerState.ERROR and event.worker.error:
            self._handle_exception(event.worker.error)

    def action_show_help(self) -> None:
        """Show the help overlay with keyboard shortcuts."""
        from dbqm.ui.modals.help import HelpModal
        self.push_screen(HelpModal())

    def action_search(self) -> None:
        """Trigger search/filter on the active QueryListWidget if present."""
        from dbqm.ui.widgets.query_list import QueryListWidget
        try:
            ql = self.query_one(QueryListWidget)
            ql.action_start_search()
        except Exception:
            pass

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar collapse state."""
        self.query_one(Sidebar).toggle_collapse()

    def action_go_back(self) -> None:
        """Go back — if showing results, return to selection; otherwise clear screen."""
        from dbqm.ui.screens.query_exec import QueryExecScreen

        # Check if a QueryExecScreen is in results phase
        try:
            exec_screen = self.query_one(QueryExecScreen)
            results_phase = exec_screen.query_one("#results-phase")
            if results_phase.display:
                exec_screen.go_back_to_selection()
                self.query_one(ActionBar).set_actions([])
                return
        except Exception:
            pass

        # Check if a GroupExecScreen is in results phase
        try:
            from dbqm.ui.screens.group_exec import GroupExecScreen
            group_screen = self.query_one(GroupExecScreen)
            results_phase = group_screen.query_one("#ge-results-phase")
            if results_phase.display:
                group_screen.go_back_to_selection()
                self.query_one(ActionBar).set_actions([])
                return
        except Exception:
            pass

        # Check if an AdhocScreen is in results phase
        try:
            from dbqm.ui.screens.adhoc import AdhocScreen
            adhoc_screen = self.query_one(AdhocScreen)
            results_phase = adhoc_screen.query_one("#adhoc-results-phase")
            if results_phase.display:
                adhoc_screen.go_back_to_input()
                self.query_one(ActionBar).set_actions([])
                return
        except Exception:
            pass

        # Check if a DDLScreen is in results phase
        try:
            from dbqm.ui.screens.ddl import DDLScreen
            ddl_screen = self.query_one(DDLScreen)
            results_phase = ddl_screen.query_one("#ddl-results-phase")
            if results_phase.display:
                ddl_screen.go_back_to_input()
                self.query_one(ActionBar).set_actions([])
                return
        except Exception:
            pass

        # Check if a BrowserScreen is in a non-select phase
        try:
            from dbqm.ui.screens.browser import BrowserScreen
            browser_screen = self.query_one(BrowserScreen)
            data_phase = browser_screen.query_one("#br-data-phase")
            if data_phase.display:
                browser_screen.go_back_to_detail()
                return
            detail_phase = browser_screen.query_one("#br-detail-phase")
            if detail_phase.display:
                browser_screen.go_back_to_list()
                return
            list_phase = browser_screen.query_one("#br-list-phase")
            if list_phase.display:
                browser_screen.go_back_to_select()
                return
        except Exception:
            pass

        # Check if a HistoryScreen is in detail phase
        try:
            from dbqm.ui.screens.history import HistoryScreen
            history_screen = self.query_one(HistoryScreen)
            detail_phase = history_screen.query_one("#hist-detail-phase")
            if detail_phase.display:
                history_screen.go_back_to_list()
                return
        except Exception:
            pass

        # Check if ConfigPortScreen is displayed (go back to Settings)
        try:
            from dbqm.ui.screens.config_port import ConfigPortScreen
            config_port = self.query_one(ConfigPortScreen)
            if config_port._initial_mode:
                config_port._go_back_to_settings()
                return
        except Exception:
            pass

        breadcrumb = self.query_one(Breadcrumb)
        if breadcrumb.path:
            breadcrumb.set_path([])
            screen_area = self.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.query_one(Sidebar).set_active("")
            self.query_one(ActionBar).set_actions([])
