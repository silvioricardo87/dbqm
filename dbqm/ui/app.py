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
        self.query_one(Breadcrumb).set_path(["Início", label])

        # Show placeholder in screen area
        screen_area = self.query_one("#screen-area", Container)
        screen_area.remove_children()
        screen_area.mount(Static(f"[dim]{label}[/dim] (em construção)", id="placeholder"))

    def action_toggle_sidebar(self) -> None:
        """Toggle sidebar collapse state."""
        self.query_one(Sidebar).toggle_collapse()

    def action_go_back(self) -> None:
        """Go back — pop breadcrumb and clear screen area."""
        breadcrumb = self.query_one(Breadcrumb)
        if breadcrumb.path:
            breadcrumb.set_path([])
            screen_area = self.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.query_one(Sidebar).set_active("")
