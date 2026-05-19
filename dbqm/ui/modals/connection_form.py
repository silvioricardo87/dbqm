"""Modal form for creating/editing database connections."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static, Select, TextArea
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
    """Modal for creating or editing a database connection."""

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
    ConnectionFormModal #form-scroll {
        height: 1fr;
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
        height: auto;
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
    ConnectionFormModal #field-description {
        height: 5;
        width: 100%;
        border: round $accent;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, connection: dict | None = None) -> None:
        super().__init__()
        self._connection = connection
        self._edit_mode = connection is not None
        self._current_db_type: str = ""
        self._current_oracle_mode: str = ""
        # Direct references to field widgets (avoids ID conflicts)
        self._fields: dict[str, Input | Select] = {}

    def compose(self) -> ComposeResult:
        conn = self._connection or {}
        title = "Editar Conexao" if self._edit_mode else "Nova Conexao"

        with Vertical(id="dialog"):
            with VerticalScroll(id="form-scroll"):
                yield Static(title, id="form-title")

                yield Static("Nome:", classes="field-label")
                name_input = Input(value=conn.get("name", ""), disabled=self._edit_mode)
                self._fields["name"] = name_input
                yield name_input

                yield Static("Tipo de banco:", classes="field-label")
                current_type = conn.get("db_type", "")
                valid_types = [v for _, v in DB_TYPE_OPTIONS]
                if current_type in valid_types:
                    db_select = Select(DB_TYPE_OPTIONS, value=current_type, id="field-db-type")
                else:
                    db_select = Select(DB_TYPE_OPTIONS, prompt="Selecione o tipo", id="field-db-type")
                self._fields["db_type"] = db_select
                yield db_select

                yield Vertical(id="dynamic-fields")

                yield Static("Descricao (opcional):", classes="field-label")
                description_area = TextArea(
                    text=conn.get("description", ""),
                    id="field-description",
                )
                self._fields["description"] = description_area
                yield description_area

            yield Static("", id="test-result")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="btn-save")
                yield Button("Testar", variant="warning", id="btn-test")
                yield Button("Cancelar", variant="default", id="btn-cancel")

    def on_mount(self) -> None:
        if self._edit_mode and self._connection:
            db_type = self._connection.get("db_type", "")
            if db_type:
                self._build_fields_for_type(db_type)
        self._fields["name"].focus()

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "field-db-type":
            db_type = str(event.value) if event.value != Select.BLANK else ""
            if db_type == self._current_db_type:
                return
            self._build_fields_for_type(db_type)
        elif event.select is self._fields.get("oracle_mode"):
            mode = str(event.value)
            if mode == self._current_oracle_mode:
                return
            self._build_oracle_detail(mode)

    def _build_fields_for_type(self, db_type: str) -> None:
        """Rebuild all dynamic fields for the selected db type."""
        self._current_db_type = db_type
        self._current_oracle_mode = ""

        container = self.query_one("#dynamic-fields", Vertical)
        # Remove old field references (preserve top-level fields that live outside the dynamic container)
        for key in list(self._fields):
            if key not in ("name", "db_type", "description"):
                self._fields.pop(key, None)
        container.remove_children()

        conn = self._connection or {}

        if db_type == "oracle":
            self._build_oracle_fields(container, conn)
        elif db_type in ("sqlserver", "postgresql", "mysql"):
            self._build_generic_fields(container, conn, db_type)

    def _build_oracle_fields(self, container: Vertical, conn: dict) -> None:
        current_mode = conn.get("mode", "direct")
        valid_modes = [v for _, v in ORACLE_MODE_OPTIONS]
        if current_mode not in valid_modes:
            current_mode = "direct"

        container.mount(Static("Modo:", classes="field-label"))
        mode_select = Select(ORACLE_MODE_OPTIONS, value=current_mode)
        self._fields["oracle_mode"] = mode_select
        container.mount(mode_select)

        # Build detail fields inline
        self._current_oracle_mode = current_mode
        self._mount_oracle_detail_fields(container, current_mode, conn)

    def _build_oracle_detail(self, mode: str) -> None:
        """Rebuild oracle detail when mode changes (tns <-> direct)."""
        self._current_oracle_mode = mode
        container = self.query_one("#dynamic-fields", Vertical)

        # Remove everything except the mode label and selector (first 2 children)
        children = list(container.children)
        for child in children[2:]:
            child.remove()

        # Remove old field refs
        for key in list(self._fields):
            if key not in ("name", "db_type", "oracle_mode"):
                self._fields.pop(key, None)

        conn = self._connection or {}
        self._mount_oracle_detail_fields(container, mode, conn)

    def _mount_oracle_detail_fields(self, container: Vertical, mode: str, conn: dict) -> None:
        if mode == "tns":
            from dbqm.core.paths import TNS_DIR
            default_tns = str(TNS_DIR / "tnsnames.ora")
            container.mount(Static("Caminho tnsnames.ora:", classes="field-label"))
            tns_path = Input(value=conn.get("tns_path", default_tns))
            self._fields["tns_path"] = tns_path
            container.mount(tns_path)

            container.mount(Static("TNS Name:", classes="field-label"))
            tns_name = Input(value=conn.get("tns_name", ""))
            self._fields["tns_name"] = tns_name
            container.mount(tns_name)
        else:
            container.mount(Static("Host:", classes="field-label"))
            host = Input(value=conn.get("host", ""))
            self._fields["host"] = host
            container.mount(host)

            container.mount(Static("Porta:", classes="field-label"))
            port = Input(value=str(conn.get("port", 1521)))
            self._fields["port"] = port
            container.mount(port)

            container.mount(Static("Service Name:", classes="field-label"))
            svc = Input(value=conn.get("service_name", ""))
            self._fields["service_name"] = svc
            container.mount(svc)

        container.mount(Static("Usuario:", classes="field-label"))
        user = Input(value=conn.get("user", ""))
        self._fields["user"] = user
        container.mount(user)

        container.mount(Static("Senha:", classes="field-label"))
        pwd = Input(value="", password=True,
                    placeholder="(manter atual)" if self._edit_mode else "")
        self._fields["password"] = pwd
        container.mount(pwd)

    def _build_generic_fields(self, container: Vertical, conn: dict, db_type: str) -> None:
        default_host = DEFAULT_HOSTS.get(db_type, "")
        default_port = DEFAULT_PORTS.get(db_type, "")

        container.mount(Static("Host:", classes="field-label"))
        host = Input(value=conn.get("host", default_host))
        self._fields["host"] = host
        container.mount(host)

        container.mount(Static("Porta:", classes="field-label"))
        port = Input(value=str(conn.get("port", default_port)))
        self._fields["port"] = port
        container.mount(port)

        container.mount(Static("Database:", classes="field-label"))
        db = Input(value=conn.get("database", ""))
        self._fields["database"] = db
        container.mount(db)

        container.mount(Static("Usuario:", classes="field-label"))
        user = Input(value=conn.get("user", ""))
        self._fields["user"] = user
        container.mount(user)

        container.mount(Static("Senha:", classes="field-label"))
        pwd = Input(value="", password=True,
                    placeholder="(manter atual)" if self._edit_mode else "")
        self._fields["password"] = pwd
        container.mount(pwd)

    def _collect_values(self) -> dict | None:
        """Collect all field values into a dict."""
        name = self._fields["name"].value.strip()
        if not name:
            self.notify("Nome obrigatorio.", severity="error")
            return None

        db_select = self._fields["db_type"]
        if db_select.value == Select.BLANK:
            self.notify("Selecione o tipo de banco.", severity="error")
            return None
        db_type = str(db_select.value)

        result: dict = {"name": name, "db_type": db_type}

        if db_type == "oracle":
            mode_select = self._fields.get("oracle_mode")
            result["mode"] = str(mode_select.value) if mode_select else "direct"

            if result["mode"] == "tns":
                result["tns_path"] = self._field_val("tns_path")
                result["tns_name"] = self._field_val("tns_name")
            else:
                result["host"] = self._field_val("host")
                result["port"] = self._field_int("port", 1521)
                result["service_name"] = self._field_val("service_name")
        else:
            result["host"] = self._field_val("host")
            result["port"] = self._field_int("port", int(DEFAULT_PORTS.get(db_type, "0")))
            result["database"] = self._field_val("database")

        result["user"] = self._field_val("user")
        result["password"] = self._field_val("password")
        result["description"] = self._field_text("description")

        return result

    def _field_val(self, key: str) -> str:
        inp = self._fields.get(key)
        return inp.value.strip() if inp else ""

    def _field_text(self, key: str) -> str:
        """Read a multi-line TextArea field, stripped of trailing whitespace."""
        widget = self._fields.get(key)
        if widget is None:
            return ""
        # TextArea exposes its content via .text, not .value
        text = getattr(widget, "text", getattr(widget, "value", ""))
        return text.strip()

    def _field_int(self, key: str, default: int) -> int:
        val = self._field_val(key)
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

        try:
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
        except Exception as e:
            success, msg = False, f"Erro: {e}"

        self.app.call_from_thread(self._show_test_result, success, msg)

    def _show_test_result(self, success: bool, msg: str) -> None:
        result_label = self.query_one("#test-result", Static)
        if success:
            result_label.update(f"[green]{msg}[/]")
        else:
            result_label.update(f"[red]{msg}[/]")

    def action_cancel(self) -> None:
        self.dismiss(None)
