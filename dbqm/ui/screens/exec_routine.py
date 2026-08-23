"""Screen for executing database procedures, functions, and package routines."""
from __future__ import annotations

import re
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, DataTable, Input, Label, Select, Static
from textual import work

from dbqm.ui.utils import sanitize_id, escape_markup
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.progress import ProgressIndicator


# Available object types per database engine
_OBJ_TYPES: dict[str, list[tuple[str, str]]] = {
    "oracle": [
        ("PACKAGE", "Packages"),
        ("PROCEDURE", "Procedures"),
        ("FUNCTION", "Functions"),
    ],
    "postgresql": [
        ("ROUTINE", "Routines"),
    ],
    "mysql": [
        ("ROUTINE", "Routines"),
    ],
    # sqlserver has no native packages/standalone stored procs in same model
    "sqlserver": [],
}


class ExecRoutineScreen(Vertical):
    """Screen for browsing and executing stored procedures/functions.

    Phase 1 — Connection + object type selection.
    Phase 2 — Object list (filter + DataTable).
    Phase 3 — Routine detail with parameter input + execution result.
    """

    DEFAULT_CSS = """
    ExecRoutineScreen {
        height: 1fr;
    }
    ExecRoutineScreen #er-select-phase {
        height: auto;
        margin: 1 2;
    }
    ExecRoutineScreen #er-select-phase Select {
        width: 60;
        margin-bottom: 1;
    }
    ExecRoutineScreen #er-type-bar {
        height: 3;
        padding: 0 0;
    }
    ExecRoutineScreen #er-type-bar Button {
        min-width: 10;
        margin: 0 1 0 0;
    }
    ExecRoutineScreen #er-list-phase {
        height: 1fr;
    }
    ExecRoutineScreen #er-filter-bar {
        height: 3;
        padding: 0 1;
    }
    ExecRoutineScreen #er-filter-bar Input {
        width: 40;
        margin-right: 1;
    }
    ExecRoutineScreen #er-obj-table {
        height: 1fr;
    }
    ExecRoutineScreen #er-detail-phase {
        height: 1fr;
    }
    ExecRoutineScreen #er-detail-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    ExecRoutineScreen #er-routines-table {
        height: 1fr;
        max-height: 15;
        margin: 0 1;
    }
    ExecRoutineScreen #er-param-area {
        height: auto;
        max-height: 50%;
        padding: 0 1;
    }
    ExecRoutineScreen #er-result-area {
        height: 1fr;
        padding: 1 1;
        overflow-y: auto;
    }
    ExecRoutineScreen .er-param-label {
        margin-top: 1;
    }
    ExecRoutineScreen .er-param-input {
        width: 100%;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._current_conn = None
        self._db = None
        self._obj_type = ""
        self._objects: list[str] = []
        self._selected_object = ""
        self._package_info = None
        self._selected_routine = None
        self._param_inputs: dict[str, Input] = {}

    def compose(self) -> ComposeResult:
        # One Panel per phase. Phase 3 was deliberately not subdivided into
        # three sibling panels (detail / parameters / result): its children
        # are sized in `1fr` inside a single container, and splitting them
        # up would change the height of each one and would also put a
        # focusable `VerticalScroll` inside a panel body that scrolls too —
        # nested scrolling, which traps the keyboard.
        # Phase 1: Connection + type selection
        with Panel("🔌  CONEXAO E TIPO", id="er-select-phase"):
            yield Label("Selecione a conexao:")
            yield Select([], prompt="Conexao", id="er-conn-select")
            yield Label("Tipo de objeto:", id="er-type-label")
            with Horizontal(id="er-type-bar"):
                pass  # buttons added dynamically
        yield ProgressIndicator()
        # Phase 2: Object list
        with Panel("📂  OBJETOS", id="er-list-phase"):
            with Horizontal(id="er-filter-bar"):
                yield Input(placeholder="Filtrar...", id="er-filter-input")
                yield Button("Buscar", id="er-filter-btn", variant="primary")
            yield DataTable(id="er-obj-table")
        # Phase 3: Detail + params + execution
        with Panel("▶  ROTINA", id="er-detail-phase"):
            yield Static("", id="er-detail-info")
            yield DataTable(id="er-routines-table")
            with VerticalScroll(id="er-param-area"):
                pass  # param inputs added dynamically
            yield VerticalScroll(id="er-result-area")

    def on_mount(self) -> None:
        self.query_one("#er-list-phase").display = False
        self.query_one("#er-detail-phase").display = False
        self.query_one("#er-type-label").display = False
        self.query_one("#er-type-bar").display = False
        self._load_connections()

    # ------------------------------------------------------------------
    # Phase 1: Connection + type selection
    # ------------------------------------------------------------------

    def _load_connections(self) -> None:
        from dbqm.models.connection import load_connections
        connections = load_connections()
        options = [(c.name, c.name) for c in connections]
        select = self.query_one("#er-conn-select", Select)
        select.set_options(options)
        self._connections = {c.name: c for c in connections}

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "er-conn-select" or event.value is Select.BLANK:
            return
        conn = self._connections.get(str(event.value))
        if not conn:
            return
        self._current_conn = conn
        self._show_type_buttons(conn.db_type)

    def _show_type_buttons(self, db_type: str) -> None:
        """Show available object type buttons based on db_type."""
        type_bar = self.query_one("#er-type-bar", Horizontal)
        type_bar.remove_children()

        types = _OBJ_TYPES.get(db_type, [])
        if not types:
            self.query_one("#er-type-label").display = False
            self.query_one("#er-type-bar").display = False
            self.notify(
                f"Nenhum tipo de rotina disponivel para {db_type}.",
                severity="warning",
            )
            return

        self.query_one("#er-type-label").display = True
        self.query_one("#er-type-bar").display = True
        for obj_type, label in types:
            btn = Button(label, id=f"er-type-{obj_type.lower()}", variant="default")
            type_bar.mount(btn)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id.startswith("er-type-"):
            obj_type = btn_id.removeprefix("er-type-").upper()
            # Highlight active
            for b in self.query_one("#er-type-bar", Horizontal).query(Button):
                b.variant = "default"
            event.button.variant = "primary"
            self._obj_type = obj_type
            self._load_objects(obj_type)

        elif btn_id == "er-filter-btn":
            self._apply_filter()

        elif btn_id == "er-exec-btn":
            self._execute_routine()

    # ------------------------------------------------------------------
    # Phase 2: Object list
    # ------------------------------------------------------------------

    def _load_objects(self, obj_type: str) -> None:
        self.query_one(ProgressIndicator).start(f"Listando {obj_type.lower()}s...")
        self._fetch_objects(obj_type)

    @work(thread=True)
    def _fetch_objects(self, obj_type: str) -> None:
        from dbqm.core.db_manager import get_connection
        from dbqm.core.object_browser import list_objects

        try:
            if self._db:
                try:
                    self._db.close()
                except Exception:
                    pass
            self._db = get_connection(self._current_conn)
            objects = list_objects(self._db, self._current_conn.db_type, obj_type)
            self.app.call_from_thread(self._show_objects, objects)
        except Exception as e:
            self.app.call_from_thread(self._on_error, str(e))

    def _on_error(self, msg: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro: {msg}", severity="error", timeout=8)

    def _show_objects(self, objects: list[str]) -> None:
        self.query_one(ProgressIndicator).stop()
        self._objects = objects

        self.query_one("#er-select-phase").display = False
        self.query_one("#er-list-phase").display = True
        self.query_one("#er-detail-phase").display = False

        table = self.query_one("#er-obj-table", DataTable)
        table.cursor_type = "row"
        table.clear(columns=True)
        table.add_column("Nome", key="name")
        for obj in objects:
            table.add_row(obj)

        self.query_one("#er-filter-input", Input).value = ""
        table.focus()

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([])
        except Exception:
            pass

    def _apply_filter(self) -> None:
        text = self.query_one("#er-filter-input", Input).value.strip().upper()
        table = self.query_one("#er-obj-table", DataTable)
        table.clear()
        filtered = [o for o in self._objects if text in o.upper()] if text else self._objects
        for obj in filtered:
            table.add_row(obj)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "er-filter-input":
            self._apply_filter()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        table_id = event.data_table.id
        if table_id == "er-obj-table":
            row_data = event.data_table.get_row(event.row_key)
            obj_name = str(row_data[0])
            self._selected_object = obj_name
            self._load_detail(obj_name)
        elif table_id == "er-routines-table":
            row_data = event.data_table.get_row(event.row_key)
            routine_name = str(row_data[0])
            self._select_routine(routine_name)

    # ------------------------------------------------------------------
    # Phase 3: Detail + params + execution
    # ------------------------------------------------------------------

    def _load_detail(self, obj_name: str) -> None:
        self.query_one(ProgressIndicator).start(f"Carregando {obj_name}...")
        self._fetch_detail(obj_name)

    @work(thread=True)
    def _fetch_detail(self, obj_name: str) -> None:
        from dbqm.core.object_browser import (
            list_package_routines,
            get_standalone_routine_info,
        )

        try:
            if self._obj_type == "PACKAGE":
                pkg_info = list_package_routines(
                    self._db, self._current_conn.db_type, obj_name,
                )
                self.app.call_from_thread(self._show_package_detail, pkg_info)
            elif self._obj_type in ("PROCEDURE", "FUNCTION", "ROUTINE"):
                routine_info = get_standalone_routine_info(
                    self._db, obj_name, self._obj_type,
                )
                self.app.call_from_thread(self._show_routine_detail, routine_info)
        except Exception as e:
            self.app.call_from_thread(self._on_error, str(e))

    def _show_package_detail(self, pkg_info) -> None:
        self.query_one(ProgressIndicator).stop()
        self._package_info = pkg_info

        self.query_one("#er-list-phase").display = False
        self.query_one("#er-detail-phase").display = True

        info = self.query_one("#er-detail-info", Static)
        info.update(
            f"[bold]{pkg_info.name}[/] | PACKAGE | "
            f"{len(pkg_info.routines)} rotina(s)"
        )

        # Show routines table
        rtable = self.query_one("#er-routines-table", DataTable)
        rtable.cursor_type = "row"
        rtable.display = True
        rtable.clear(columns=True)
        rtable.add_column("Rotina", key="name")
        rtable.add_column("Tipo", key="type")
        rtable.add_column("Assinatura", key="sig")
        for r in pkg_info.routines:
            rtable.add_row(r.name, r.routine_type, r.signature)

        # Clear param area and result
        self.query_one("#er-param-area", VerticalScroll).remove_children()
        result_area = self.query_one("#er-result-area", VerticalScroll)
        result_area.remove_children()

        rtable.focus()
        self._set_detail_actions()

    def _show_routine_detail(self, routine_info) -> None:
        """Show detail for standalone procedure/function — go straight to params."""
        self.query_one(ProgressIndicator).stop()
        self._selected_routine = routine_info

        self.query_one("#er-list-phase").display = False
        self.query_one("#er-detail-phase").display = True

        info = self.query_one("#er-detail-info", Static)
        info.update(
            f"[bold]{routine_info.name}[/] | {routine_info.routine_type} | "
            f"{routine_info.signature}"
        )

        # Hide routines table (not needed for standalone)
        self.query_one("#er-routines-table", DataTable).display = False

        # Build param inputs
        self._build_param_inputs(routine_info)

        result_area = self.query_one("#er-result-area", VerticalScroll)
        result_area.remove_children()

        self._set_detail_actions()

    def _select_routine(self, routine_name: str) -> None:
        """Select a routine from the package routines table."""
        if not self._package_info:
            return
        for r in self._package_info.routines:
            if r.name == routine_name:
                self._selected_routine = r
                info = self.query_one("#er-detail-info", Static)
                info.update(
                    f"[bold]{self._package_info.name}.{r.name}[/] | "
                    f"{r.routine_type} | {r.signature}"
                )
                self._build_param_inputs(r)
                self._set_detail_actions()
                break

    def _build_param_inputs(self, routine) -> None:
        """Build input fields for routine IN/IN OUT parameters."""
        param_area = self.query_one("#er-param-area", VerticalScroll)
        param_area.remove_children()
        self._param_inputs.clear()

        in_params = [p for p in routine.params if p.direction in ("IN", "IN OUT")]
        if not in_params:
            param_area.mount(Static("[dim]Sem parametros de entrada[/]", markup=True))
            param_area.mount(
                Button("Executar", id="er-exec-btn", variant="primary")
            )
            return

        for p in in_params:
            label_text = f":{p.name} ({p.direction} {p.data_type})"
            if p.default:
                label_text += f" [dim]default: {p.default}[/]"
            param_area.mount(Label(label_text, classes="er-param-label", markup=True))
            inp = Input(
                value=p.default or "",
                placeholder=p.data_type,
                id=f"er-p-{sanitize_id(p.name)}",
                classes="er-param-input",
            )
            param_area.mount(inp)
            self._param_inputs[p.name] = inp

        param_area.mount(
            Button("Executar", id="er-exec-btn", variant="primary")
        )

        # Focus first input
        if in_params:
            first_inp = self._param_inputs[in_params[0].name]
            self.call_after_refresh(first_inp.focus)

    def _set_detail_actions(self) -> None:
        try:
            action_bar = self.app.query_one(ActionBar)
            actions = [
                Action("Executar", "X", "exec_routine"),
            ]
            action_bar.set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_routine(self) -> None:
        if not self._selected_routine or not self._db:
            self.notify("Selecione uma rotina primeiro.", severity="warning")
            return

        # Collect param values
        param_values = {}
        for p_name, inp in self._param_inputs.items():
            param_values[p_name] = inp.value

        routine = self._selected_routine
        package = self._package_info.name if self._package_info and self._obj_type == "PACKAGE" else ""

        self.query_one(ProgressIndicator).start(
            f"Executando [bold]{escape_markup(routine.name)}[/]..."
        )
        self._run_routine(package, routine, param_values)

    @work(thread=True)
    def _run_routine(self, package: str, routine, param_values: dict) -> None:
        from dbqm.core.object_browser import execute_routine

        try:
            result = execute_routine(self._db, package, routine, param_values)
            self.app.call_from_thread(self._show_execution_result, result)
        except Exception as e:
            self.app.call_from_thread(self._on_error, str(e))

    def _show_execution_result(self, result) -> None:
        self.query_one(ProgressIndicator).stop()

        result_area = self.query_one("#er-result-area", VerticalScroll)
        result_area.remove_children()

        if result.success:
            lines = [f"[bold]Executado com sucesso[/] ({result.elapsed:.2f}s)"]
            if result.return_value is not None:
                lines.append(f"\n[bold]Retorno:[/] {result.return_value}")
            if result.output_lines:
                lines.append("\n[bold]Output:[/]")
                for line in result.output_lines:
                    lines.append(f"  {escape_markup(line)}")
            if not result.return_value and not result.output_lines:
                lines.append("\n[dim]Sem retorno ou output DBMS_OUTPUT[/]")
        else:
            lines = [
                f"[bold $ds-op-failure]Erro na execucao[/] ({result.elapsed:.2f}s)",
                f"\n[$ds-op-failure]{escape_markup(result.error)}[/]",
            ]

        result_area.mount(Static("\n".join(lines), markup=True))

    # ------------------------------------------------------------------
    # Action bar handler
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        if message.action_id == "exec_routine":
            self._execute_routine()

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    def go_back(self) -> bool:
        """Handle back navigation between phases. Returns True if handled."""
        if self.query_one("#er-detail-phase").display:
            if self._obj_type == "PACKAGE":
                self.query_one("#er-detail-phase").display = False
                self.query_one("#er-list-phase").display = True
                self._selected_routine = None
                self._package_info = None
                self.query_one("#er-obj-table", DataTable).focus()
            else:
                self.query_one("#er-detail-phase").display = False
                self.query_one("#er-list-phase").display = True
                self._selected_routine = None
                self.query_one("#er-obj-table", DataTable).focus()
            try:
                self.app.query_one(ActionBar).set_actions([])
            except Exception:
                pass
            return True
        elif self.query_one("#er-list-phase").display:
            self.query_one("#er-list-phase").display = False
            self.query_one("#er-select-phase").display = True
            self._objects = []
            self._selected_object = ""
            if self._db:
                try:
                    self._db.close()
                except Exception:
                    pass
                self._db = None
            try:
                self.app.query_one(ActionBar).set_actions([])
            except Exception:
                pass
            # Hand focus back to the connection select so the keyboard keeps
            # working in the select phase (otherwise it stays on the now-hidden
            # object table).
            try:
                from textual.widgets import Select
                self.query_one("#er-conn-select", Select).focus()
            except Exception:
                pass
            return True
        return False
