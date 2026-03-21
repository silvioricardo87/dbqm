"""Modal form for creating/editing database connections."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, Select
from textual import work


DB_TYPE_OPTIONS = [
    ("Oracle", "oracle"),
    ("SQL Server", "sqlserver"),
    ("PostgreSQL", "postgresql"),
    ("MySQL", "mysql"),
]

ORACLE_MODE_OPTIONS = [
    ("Conexao direta (host/port/service)", "direct"),
    ("TNS (tnsnames.ora)", "tns"),
]

DEFAULT_PORTS = {
    "oracle": "1521",
    "sqlserver": "1433",
    "postgresql": "5432",
    "mysql": "3306",
}

DEFAULT_HOSTS = {
    "postgresql": "localhost",
    "mysql": "localhost",
}


class ConnectionFormModal(ModalScreen[dict | None]):
    """Modal for creating or editing a database connection.

    Dismisses with a dict of field values on save, or None on cancel/ESC.
    """

    DEFAULT_CSS = """
    ConnectionFormModal {
        align: center middle;
    }

    ConnectionFormModal #dialog {
        width: 70;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ConnectionFormModal #form-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    ConnectionFormModal .field-label {
        margin-top: 1;
        height: 1;
    }

    ConnectionFormModal Input {
        width: 100%;
    }

    ConnectionFormModal Select {
        width: 100%;
    }

    ConnectionFormModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }

    ConnectionFormModal Button {
        margin: 0 1;
    }

    ConnectionFormModal #test-result {
        margin-top: 1;
        height: auto;
        width: 100%;
    }

    ConnectionFormModal #dynamic-fields {
        height: auto;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, connection: dict | None = None) -> None:
        super().__init__()
        self._connection = connection
        self._edit_mode = connection is not None

    def compose(self) -> ComposeResult:
        conn = self._connection or {}
        title = "Editar Conexao" if self._edit_mode else "Nova Conexao"

        with Vertical(id="dialog"):
            yield Static(title, id="form-title")

            # Name
            yield Static("Nome:", classes="field-label")
            yield Input(
                value=conn.get("name", ""),
                id="field-name",
                disabled=self._edit_mode,
            )

            # DB Type
            yield Static("Tipo de banco:", classes="field-label")
            current_type = conn.get("db_type", Select.BLANK)
            yield Select(
                DB_TYPE_OPTIONS,
                value=current_type,
                id="field-db-type",
                allow_blank=not self._edit_mode,
            )

            # Dynamic fields container
            yield Vertical(id="dynamic-fields")

            # Test result area
            yield Static("", id="test-result")

            # Buttons
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="btn-save")
                yield Button("Testar", variant="warning", id="btn-test")
                yield Button("Cancelar", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        if self._edit_mode and self._connection:
            self._rebuild_fields(self._connection.get("db_type", ""))
        self.query_one("#field-name", Input).focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "field-db-type":
            db_type = event.value if event.value != Select.BLANK else ""
            self._rebuild_fields(str(db_type))
        elif event.select.id == "field-oracle-mode":
            self._rebuild_oracle_detail(str(event.value))

    def _rebuild_fields(self, db_type: str) -> None:
        """Clear and re-populate the dynamic fields container."""
        container = self.query_one("#dynamic-fields", Vertical)
        container.remove_children()

        conn = self._connection or {}

        if db_type == "oracle":
            self._mount_oracle_fields(container, conn)
        elif db_type in ("sqlserver", "postgresql", "mysql"):
            self._mount_generic_fields(container, conn, db_type)

    def _mount_oracle_fields(self, container: Vertical, conn: dict) -> None:
        """Mount Oracle-specific fields."""
        current_mode = conn.get("mode", "direct")

        container.mount(Static("Modo:", classes="field-label"))
        container.mount(
            Select(
                ORACLE_MODE_OPTIONS,
                value=current_mode,
                id="field-oracle-mode",
                allow_blank=False,
            )
        )
        # Sub-container for mode-specific fields
        sub = Vertical(id="oracle-detail")
        container.mount(sub)

        self.call_later(self._rebuild_oracle_detail, current_mode)

    def _rebuild_oracle_detail(self, mode: str) -> None:
        """Rebuild Oracle detail fields based on mode (tns or direct)."""
        try:
            detail = self.query_one("#oracle-detail", Vertical)
        except Exception:
            return
        detail.remove_children()

        conn = self._connection or {}

        if mode == "tns":
            from pathlib import Path
            default_tns = str(
                Path(__file__).resolve().parent.parent.parent.parent / "tns" / "tnsnames.ora"
            )
            detail.mount(Static("Caminho tnsnames.ora:", classes="field-label"))
            detail.mount(Input(value=conn.get("tns_path", default_tns), id="field-tns-path"))
            detail.mount(Static("TNS Name:", classes="field-label"))
            detail.mount(Input(value=conn.get("tns_name", ""), id="field-tns-name"))
        else:
            detail.mount(Static("Host:", classes="field-label"))
            detail.mount(Input(value=conn.get("host", ""), id="field-host"))
            detail.mount(Static("Porta:", classes="field-label"))
            detail.mount(Input(value=str(conn.get("port", 1521)), id="field-port"))
            detail.mount(Static("Service Name:", classes="field-label"))
            detail.mount(Input(value=conn.get("service_name", ""), id="field-service-name"))

        # Common auth fields
        detail.mount(Static("Usuario:", classes="field-label"))
        detail.mount(Input(value=conn.get("user", ""), id="field-user"))
        detail.mount(Static("Senha:", classes="field-label"))
        detail.mount(Input(
            value="",
            id="field-password",
            password=True,
            placeholder="(manter atual)" if self._edit_mode else "",
        ))

    def _mount_generic_fields(self, container: Vertical, conn: dict, db_type: str) -> None:
        """Mount fields for SQL Server, PostgreSQL, MySQL."""
        default_host = DEFAULT_HOSTS.get(db_type, "")
        default_port = DEFAULT_PORTS.get(db_type, "")

        container.mount(Static("Host:", classes="field-label"))
        container.mount(Input(value=conn.get("host", default_host), id="field-host"))
        container.mount(Static("Porta:", classes="field-label"))
        container.mount(Input(value=str(conn.get("port", default_port)), id="field-port"))
        container.mount(Static("Database:", classes="field-label"))
        container.mount(Input(value=conn.get("database", ""), id="field-database"))
        container.mount(Static("Usuario:", classes="field-label"))
        container.mount(Input(value=conn.get("user", ""), id="field-user"))
        container.mount(Static("Senha:", classes="field-label"))
        container.mount(Input(
            value="",
            id="field-password",
            password=True,
            placeholder="(manter atual)" if self._edit_mode else "",
        ))

    def _collect_values(self) -> dict | None:
        """Collect all field values into a dict. Returns None if validation fails."""
        try:
            name = self.query_one("#field-name", Input).value.strip()
        except Exception:
            return None

        if not name:
            self.notify("Nome obrigatorio.", severity="error")
            return None

        db_type_select = self.query_one("#field-db-type", Select)
        if db_type_select.value == Select.BLANK:
            self.notify("Selecione o tipo de banco.", severity="error")
            return None
        db_type = str(db_type_select.value)

        result: dict = {"name": name, "db_type": db_type}

        if db_type == "oracle":
            try:
                mode_select = self.query_one("#field-oracle-mode", Select)
                result["mode"] = str(mode_select.value)
            except Exception:
                result["mode"] = "direct"

            if result["mode"] == "tns":
                result["tns_path"] = self._get_input("#field-tns-path")
                result["tns_name"] = self._get_input("#field-tns-name")
            else:
                result["host"] = self._get_input("#field-host")
                result["port"] = self._get_input_int("#field-port", 1521)
                result["service_name"] = self._get_input("#field-service-name")
        else:
            result["host"] = self._get_input("#field-host")
            result["port"] = self._get_input_int("#field-port", int(DEFAULT_PORTS.get(db_type, "0")))
            result["database"] = self._get_input("#field-database")

        result["user"] = self._get_input("#field-user")
        result["password"] = self._get_input("#field-password")

        return result

    def _get_input(self, selector: str) -> str:
        try:
            return self.query_one(selector, Input).value.strip()
        except Exception:
            return ""

    def _get_input_int(self, selector: str, default: int) -> int:
        val = self._get_input(selector)
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            values = self._collect_values()
            if values is not None:
                self.dismiss(values)
        elif event.button.id == "btn-test":
            self._do_test()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def _do_test(self) -> None:
        """Test the connection using collected field values."""
        values = self._collect_values()
        if values is None:
            return

        result_label = self.query_one("#test-result", Static)
        result_label.update("[dim]Testando conexao...[/]")
        self._run_test(values)

    @work(thread=True)
    def _run_test(self, values: dict) -> None:
        from dbqm.core.crypto import encrypt
        from dbqm.core.db_manager import test_connection
        from dbqm.models.connection import Connection

        # Build a Connection object for testing
        password = values.get("password", "")
        if password:
            password = encrypt(password)
        elif self._edit_mode and self._connection:
            password = self._connection.get("password", "")

        conn = Connection(
            name=values["name"],
            db_type=values["db_type"],
            user=values.get("user", ""),
            password=password,
            mode=values.get("mode"),
            host=values.get("host"),
            port=values.get("port"),
            service_name=values.get("service_name"),
            database=values.get("database"),
            tns_path=values.get("tns_path"),
            tns_name=values.get("tns_name"),
        )

        success, msg = test_connection(conn)
        self.call_from_thread(self._show_test_result, success, msg)

    def _show_test_result(self, success: bool, msg: str) -> None:
        result_label = self.query_one("#test-result", Static)
        if success:
            result_label.update(f"[green]{msg}[/]")
        else:
            result_label.update(f"[red]{msg}[/]")

    def action_cancel(self) -> None:
        self.dismiss(None)
