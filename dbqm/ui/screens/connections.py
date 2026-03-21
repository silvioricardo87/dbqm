"""Connection management screen."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected


DB_TYPE_LABELS = {
    "oracle": "Oracle",
    "sqlserver": "SQL Server",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
}


class ConnectionsScreen(Vertical):
    """Screen widget for managing database connections."""

    DEFAULT_CSS = """
    ConnectionsScreen {
        height: 1fr;
    }
    ConnectionsScreen #conn-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    ConnectionsScreen DataTable {
        height: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(
            "[dim]Nenhuma conexao configurada[/]",
            id="conn-empty",
            markup=True,
        )
        yield DataTable(id="conn-table")

    def on_mount(self) -> None:
        self._setup_table()
        self._load_connections()
        self._set_actions()

    def _setup_table(self) -> None:
        table = self.query_one("#conn-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("#", "Nome", "Tipo", "Destino")

    def _load_connections(self) -> None:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        table = self.query_one("#conn-table", DataTable)
        empty_msg = self.query_one("#conn-empty", Static)

        table.clear()

        if not connections:
            empty_msg.display = True
            table.display = False
            return

        empty_msg.display = False
        table.display = True

        for i, conn in enumerate(connections, 1):
            db_label = DB_TYPE_LABELS.get(conn.db_type, conn.db_type)
            if conn.db_type == "oracle" and conn.mode == "tns":
                db_label = "Oracle/TNS"
            table.add_row(str(i), conn.name, db_label, conn.display_target())

    def _set_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return
        actions = [
            Action("Nova", "N", "conn_new"),
            Action("Testar", "T", "conn_test"),
            Action("Editar", "E", "conn_edit"),
            Action("Renomear", "R", "conn_rename"),
            Action("Remover", "D", "conn_remove"),
        ]
        action_bar.set_actions(actions)

    def _get_selected_name(self) -> str | None:
        """Get the connection name from the currently selected table row."""
        table = self.query_one("#conn-table", DataTable)
        if not table.display or table.row_count == 0:
            return None
        try:
            row_key = table.cursor_row
            row = table.get_row_at(row_key)
            return str(row[1])  # Name column
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id
        if action == "conn_new":
            self._handle_new()
        elif action == "conn_test":
            self._handle_test()
        elif action == "conn_edit":
            self._handle_edit()
        elif action == "conn_rename":
            self._handle_rename()
        elif action == "conn_remove":
            self._handle_remove()

    # -- New --

    def _handle_new(self) -> None:
        from dbqm.ui.modals.connection_form import ConnectionFormModal

        modal = ConnectionFormModal()
        self.app.push_screen(modal, callback=self._on_new_result)

    def _on_new_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.core.crypto import encrypt
        from dbqm.models.connection import Connection, load_connections, save_connections

        connections = load_connections()

        # Check duplicate
        if any(c.name == result["name"] for c in connections):
            self.notify(f'Conexao "{result["name"]}" ja existe.', severity="error")
            return

        password = result.get("password", "")
        if password:
            password = encrypt(password)

        conn = Connection(
            name=result["name"],
            db_type=result["db_type"],
            user=result.get("user", ""),
            password=password,
            mode=result.get("mode"),
            host=result.get("host"),
            port=result.get("port"),
            service_name=result.get("service_name"),
            database=result.get("database"),
            tns_path=result.get("tns_path"),
            tns_name=result.get("tns_name"),
        )
        connections.append(conn)
        save_connections(connections)
        self._load_connections()
        self._update_status_bar()
        self.notify(f'Conexao "{conn.name}" criada!')

    # -- Test --

    def _handle_test(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return
        self.notify(f"Testando {name}...")
        self._run_test(name)

    @work(thread=True)
    def _run_test(self, name: str) -> None:
        from dbqm.core.db_manager import test_connection
        from dbqm.models.connection import find_connection

        conn = find_connection(name)
        if conn is None:
            self.call_from_thread(
                self.notify, f'Conexao "{name}" nao encontrada.', severity="error"
            )
            return

        success, msg = test_connection(conn)
        severity = "information" if success else "error"
        self.call_from_thread(self.notify, msg, severity=severity, timeout=6)

    # -- Edit --

    def _handle_edit(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        from dbqm.models.connection import find_connection
        from dbqm.ui.modals.connection_form import ConnectionFormModal

        conn = find_connection(name)
        if conn is None:
            self.notify(f'Conexao "{name}" nao encontrada.', severity="error")
            return

        conn_dict = conn.to_dict()
        modal = ConnectionFormModal(connection=conn_dict)
        self.app.push_screen(modal, callback=self._on_edit_result)

    def _on_edit_result(self, result: dict | None) -> None:
        if result is None:
            return

        from dbqm.core.crypto import encrypt
        from dbqm.models.connection import load_connections, save_connections

        connections = load_connections()
        name = result["name"]

        for conn in connections:
            if conn.name == name:
                conn.db_type = result["db_type"]
                conn.user = result.get("user", "")
                conn.mode = result.get("mode")
                conn.host = result.get("host")
                conn.port = result.get("port")
                conn.service_name = result.get("service_name")
                conn.database = result.get("database")
                conn.tns_path = result.get("tns_path")
                conn.tns_name = result.get("tns_name")

                password = result.get("password", "")
                if password:
                    conn.password = encrypt(password)
                # If password is empty, keep existing
                break

        save_connections(connections)
        self._load_connections()
        self.notify(f'Conexao "{name}" atualizada!')

    # -- Rename --

    def _handle_rename(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        from dbqm.ui.modals.text_input import TextInputModal

        modal = TextInputModal(title="Renomear Conexao", message=f'Novo nome para "{name}":', default=name)
        self._rename_old_name = name
        self.app.push_screen(modal, callback=self._on_rename_result)

    def _on_rename_result(self, new_name: str | None) -> None:
        if new_name is None or not new_name.strip():
            return

        new_name = new_name.strip()
        old_name = self._rename_old_name

        if new_name == old_name:
            return

        from dbqm.models.connection import load_connections, save_connections

        connections = load_connections()

        if any(c.name == new_name for c in connections):
            self.notify(f'Conexao "{new_name}" ja existe.', severity="error")
            return

        for conn in connections:
            if conn.name == old_name:
                conn.name = new_name
                break
        save_connections(connections)

        # Update queries that reference the old name
        from dbqm.models.query import load_queries, save_queries

        queries = load_queries()
        updated = False
        for q in queries:
            if q.connection == old_name:
                q.connection = new_name
                updated = True
        if updated:
            save_queries(queries)

        self._load_connections()
        self.notify(f'Conexao renomeada: "{old_name}" -> "{new_name}"')

    # -- Remove --

    def _handle_remove(self) -> None:
        name = self._get_selected_name()
        if name is None:
            self.notify("Selecione uma conexao.", severity="warning")
            return

        from dbqm.ui.modals.confirm import ConfirmModal

        self._remove_name = name
        modal = ConfirmModal(message=f'Remover conexao "{name}"?')
        self.app.push_screen(modal, callback=self._on_remove_result)

    def _on_remove_result(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.models.connection import delete_connection

        name = self._remove_name
        if delete_connection(name):
            self._load_connections()
            self._update_status_bar()
            self.notify(f'Conexao "{name}" removida!')
        else:
            self.notify(f'Conexao "{name}" nao encontrada.', severity="error")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _update_status_bar(self) -> None:
        """Update the status bar counts."""
        try:
            from dbqm.models.connection import load_connections
            from dbqm.models.query import load_queries
            from dbqm.models.group import load_groups
            from dbqm.ui.widgets.status_bar import StatusBar

            status_bar = self.app.query_one(StatusBar)
            status_bar.update_counts(
                connections=len(load_connections()),
                queries=len(load_queries()),
                groups=len(load_groups()),
            )
        except Exception:
            pass
