"""Main Textual application for DB Query Manager."""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, Container
from textual.widgets import Header, Static

from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT
from dbqm.ui.widgets.sidebar import Sidebar, SidebarItemSelected
from dbqm.ui.widgets.breadcrumb import Breadcrumb
from dbqm.ui.widgets.status_bar import StatusBar
from dbqm.ui.widgets.action_bar import ActionBar


# Map sidebar actions to breadcrumb labels
ACTION_LABELS: dict[str, str] = {
    "exec_query": "Executar Consulta",
    "adhoc_sql": "SQL Avulso",
    "config_query": "Gerenciar Consultas",
    "exec_group": "Executar Grupo",
    "config_group": "Gerenciar Grupos",
    "extract_ddl": "DDL",
    "browse": "Objetos",
    "history": "Histórico",
    "config_conn": "Conexões",
    "portability": "Exportar/Importar",
    "settings": "Configurações",
}


class DBQMApp(App):
    """DB Query Manager — main application."""

    TITLE = "DB Query Manager v1.0"

    BINDINGS = [
        Binding("ctrl+b", "toggle_sidebar", "Toggle sidebar"),
        Binding("ctrl+q", "quit", "Quit"),
        Binding("escape", "go_back", "Back"),
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
        system_actions = {"config_conn", "portability", "settings"}
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

        if action == "exec_query":
            from dbqm.ui.screens.query_exec import QueryExecScreen
            screen_area.mount(QueryExecScreen(id="query-exec-screen"))
        elif action == "exec_group":
            from dbqm.ui.screens.group_exec import GroupExecScreen
            self.query_one(Breadcrumb).set_path(["Grupos", "Executar"])
            screen_area.mount(GroupExecScreen(id="group-exec-screen"))
        elif action == "config_query":
            from dbqm.ui.screens.query_manage import QueryManageScreen
            screen_area.mount(QueryManageScreen(id="query-manage-screen"))
        elif action == "config_group":
            from dbqm.ui.screens.group_manage import GroupManageScreen
            screen_area.mount(GroupManageScreen(id="group-manage-screen"))
        elif action == "adhoc_sql":
            from dbqm.ui.screens.adhoc import AdhocScreen
            self.query_one(Breadcrumb).set_path(["Consultas", "SQL avulso"])
            screen_area.mount(AdhocScreen(id="adhoc-screen"))
        elif action == "extract_ddl":
            from dbqm.ui.screens.ddl import DDLScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "DDL"])
            screen_area.mount(DDLScreen(id="ddl-screen"))
        elif action == "browse":
            from dbqm.ui.screens.browser import BrowserScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "Objetos"])
            screen_area.mount(BrowserScreen(id="browser-screen"))
        elif action == "history":
            from dbqm.ui.screens.history import HistoryScreen
            self.query_one(Breadcrumb).set_path(["Ferramentas", "Historico"])
            screen_area.mount(HistoryScreen(id="history-screen"))
        elif action == "config_conn":
            from dbqm.ui.screens.connections import ConnectionsScreen
            screen_area.mount(ConnectionsScreen(id="connections-screen"))
        else:
            screen_area.mount(Static(f"[dim]{label}[/dim] (em construção)", id="placeholder"))

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

        breadcrumb = self.query_one(Breadcrumb)
        if breadcrumb.path:
            breadcrumb.set_path([])
            screen_area = self.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.query_one(Sidebar).set_active("")
            self.query_one(ActionBar).set_actions([])
