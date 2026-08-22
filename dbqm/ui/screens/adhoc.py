"""Ad-hoc SQL execution screen — type SQL, execute, view results."""
from __future__ import annotations

import re
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Checkbox, ContentSwitcher, Select, Static, TextArea
from dbqm.ui.utils import NavSelect
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.result_table import ResultTable
from dbqm.ui.widgets.sql_viewer import SqlViewer

from dbqm.core.query_engine import (
    QueryResult,
    AdhocResult,
    classify_sql,
    detect_params,
    replace_literals_with_params,
    parse_sql,
    parse_dml_literals,
    execute_adhoc,
    generate_sql_text,
)


def _format_plsql_message(result: AdhocResult) -> str:
    """Build the Rich markup shown after a PL/SQL block executes.

    Only the success header — DBMS_OUTPUT lines render in the dedicated panel.
    """
    return f"[bold]Bloco PL/SQL executado[/] ({result.elapsed:.2f}s)"


class AdhocScreen(Vertical):
    """Screen widget for executing ad-hoc SQL statements.

    Three simultaneous panels (no phase swap):
      - PARAMETROS  — connection selector + DBMS_OUTPUT opt-in.
      - SQL EDITOR  — the SQL TextArea plus the action buttons.
      - RESULTADOS  — a Tabela/Output sub-toggle (ContentSwitcher) hosting the
        ResultTable (#res-table) and the DBMS/output view (#res-output).
    """

    DEFAULT_CSS = """
    AdhocScreen {
        height: 1fr;
    }
    AdhocScreen #adhoc-body {
        height: 1fr;
    }
    AdhocScreen #adhoc-params-panel {
        width: 32;
    }
    AdhocScreen #adhoc-editor-col {
        width: 1fr;
    }
    AdhocScreen #adhoc-conn-select {
        width: 100%;
        border: round $error;
    }
    AdhocScreen #adhoc-conn-select.--conn-selected {
        border: round $success;
    }
    AdhocScreen #adhoc-dbms-toggle {
        width: 100%;
        height: auto;
        margin: 1 0 0 0;
        padding: 0 1;
        border: round $primary;
        background: $surface;
        content-align: left middle;
    }
    AdhocScreen #adhoc-editor-panel {
        height: 3fr;
    }
    AdhocScreen #adhoc-sql-area {
        height: 1fr;
    }
    AdhocScreen #adhoc-btn-bar {
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }
    AdhocScreen #adhoc-btn-bar Button {
        margin: 0 1;
    }
    AdhocScreen #adhoc-results-panel {
        height: 2fr;
    }
    AdhocScreen #res-toggle-bar {
        height: auto;
        padding: 0 0 1 0;
    }
    AdhocScreen #res-toggle-bar Button {
        margin: 0 1 0 0;
    }
    AdhocScreen #adhoc-result-info {
        height: auto;
        padding: 0 1;
        color: $text-muted;
    }
    AdhocScreen #res-switcher {
        height: 1fr;
    }
    AdhocScreen #adhoc-dml-result {
        height: auto;
        padding: 1 2;
        content-align: center middle;
        text-align: center;
    }
    AdhocScreen #adhoc-dbms-panel {
        height: 1fr;
        padding: 0;
    }
    AdhocScreen #adhoc-dbms-label {
        height: auto;
        color: $text-muted;
    }
    AdhocScreen #adhoc-dbms-view {
        height: 1fr;
        min-height: 6;
        margin: 0;
    }
    AdhocScreen #adhoc-dbms-btns {
        height: auto;
        padding: 1 0;
        align: left middle;
    }
    AdhocScreen #adhoc-dbms-btns Button {
        margin: 0 1 0 0;
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
        self._current_sql = ""
        self._current_params: dict[str, str] = {}
        self._current_result: QueryResult | None = None
        self._current_adhoc_result: AdhocResult | None = None
        self._sql_type = ""
        self._table_name = ""
        self._query_params = []  # list of QueryParam
        self._db_connection = None  # for DML commit/rollback
        self._capture_output = False  # DBMS_OUTPUT opt-in for this execution
        self._dbms_output_lines: list[str] = []
        self._current_sql = ""  # raw SQL of the last execution (for evidence)
        self._last_exec_at = ""  # timestamp of the last execution (for evidence)

    def on_key(self, event) -> None:
        """Handle Ctrl+Enter and Ctrl+L shortcuts."""
        if event.key == "ctrl+enter":
            event.prevent_default()
            event.stop()
            if not self.query_one("#adhoc-execute", Button).disabled:
                self._handle_execute()
        elif event.key == "ctrl+l":
            event.prevent_default()
            event.stop()
            self._handle_clear()

    def compose(self) -> ComposeResult:
        with Horizontal(id="adhoc-body"):
            # Left column — parameters / connection / DBMS opt-in.
            with Panel("🎯  PARAMETROS", accent=True, id="adhoc-params-panel"):
                yield NavSelect([], prompt="Selecione a conexao", id="adhoc-conn-select")
                yield Checkbox("Saida DBMS", id="adhoc-dbms-toggle", value=False)

            # Right column — editor above, results below.
            with Vertical(id="adhoc-editor-col"):
                with Panel("✏️  SQL EDITOR", id="adhoc-editor-panel"):
                    yield TextArea("", language="sql", id="adhoc-sql-area")
                    with Horizontal(id="adhoc-btn-bar"):
                        yield Button("Executar (Ctrl+Enter)", variant="primary", id="adhoc-execute", disabled=True)
                        yield Button("Limpar (Ctrl+L)", variant="error", id="adhoc-clear")
                        yield Button("Gerar SQL", variant="default", id="adhoc-generate")
                        yield Button("Salvar como consulta", variant="default", id="adhoc-save")

                with Panel("📊  RESULTADOS", id="adhoc-results-panel"):
                    with Horizontal(id="res-toggle-bar"):
                        yield Button("Tabela", id="res-btn-table")
                        yield Button("Output", id="res-btn-output")
                    yield Static("", id="adhoc-result-info")
                    with ContentSwitcher(initial="res-table", id="res-switcher"):
                        yield ResultTable(id="res-table")
                        with Vertical(id="res-output"):
                            yield Static("", id="adhoc-dml-result")
                            yield SqlViewer("", id="adhoc-sql-viewer")
                            with Vertical(id="adhoc-dbms-panel"):
                                yield Static("DBMS_OUTPUT", id="adhoc-dbms-label")
                                yield TextArea("", read_only=True, id="adhoc-dbms-view")
                                with Horizontal(id="adhoc-dbms-btns"):
                                    yield Button("Salvar em arquivo", id="adhoc-dbms-save")
                                    yield Button("Copiar", id="adhoc-dbms-copy")

        # Progress indicator
        yield ProgressIndicator()

    def on_mount(self) -> None:
        self.query_one("#adhoc-dml-result").display = False
        self.query_one("#adhoc-sql-viewer").display = False
        self.query_one("#adhoc-dbms-panel").display = False
        self._load_connections()
        self.call_after_refresh(self._set_initial_focus)

    def _show_results(self, view: str) -> None:
        """Flip the results sub-toggle to 'res-table' or 'res-output'."""
        self.query_one("#res-switcher", ContentSwitcher).current = view

    def _dbms_output_enabled(self) -> bool:
        """Whether the user opted into DBMS_OUTPUT capture via the checkbox."""
        try:
            return bool(self.query_one("#adhoc-dbms-toggle", Checkbox).value)
        except Exception:
            return False

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#adhoc-sql-area", TextArea).focus()
        except Exception:
            pass

    def _has_connection(self) -> bool:
        """Check if a valid connection is selected."""
        val = self.query_one("#adhoc-conn-select", Select).value
        return isinstance(val, str)

    def _update_execute_button(self) -> None:
        """Enable/disable Execute button based on connection + SQL content."""
        has_conn = self._has_connection()
        has_sql = bool(self.query_one("#adhoc-sql-area", TextArea).text.strip())
        self.query_one("#adhoc-execute", Button).disabled = not (has_conn and has_sql)

    def on_select_changed(self, event: Select.Changed) -> None:
        """React to connection selection changes."""
        select_widget = self.query_one("#adhoc-conn-select", Select)
        if self._has_connection():
            select_widget.add_class("--conn-selected")
        else:
            select_widget.remove_class("--conn-selected")
        self._update_execute_button()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """React to SQL text changes."""
        self._update_execute_button()

    def _load_connections(self) -> None:
        """Load connections into the Select widget."""
        from dbqm.models.connection import load_connections

        connections = load_connections()
        options = [
            (f"{c.name} ({c.db_type} - {c.display_target()})", c.name)
            for c in connections
        ]
        select_widget = self.query_one("#adhoc-conn-select", Select)
        select_widget.set_options(options)

    def _get_selected_conn(self):
        """Get the currently selected connection object."""
        from dbqm.models.connection import find_connection

        select_widget = self.query_one("#adhoc-conn-select", Select)
        conn_name = select_widget.value
        if conn_name is Select.BLANK:
            self.notify("Selecione uma conexao.", severity="warning")
            return None
        conn = find_connection(conn_name)
        if not conn:
            self.notify("Conexao nao encontrada.", severity="error")
            return None
        return conn

    def _get_sql(self) -> str:
        """Get SQL text from the TextArea."""
        return self.query_one("#adhoc-sql-area", TextArea).text.strip()

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "adhoc-execute":
            self._handle_execute()
        elif btn_id == "adhoc-clear":
            self._handle_clear()
        elif btn_id == "adhoc-generate":
            self._handle_generate()
        elif btn_id == "adhoc-save":
            self._handle_save()
        elif btn_id == "adhoc-commit":
            self._handle_commit()
        elif btn_id == "adhoc-rollback":
            self._handle_rollback()
        elif btn_id == "adhoc-dbms-save":
            self._handle_dbms_save()
        elif btn_id == "adhoc-dbms-copy":
            self._copy_dbms_output()
        elif btn_id == "res-btn-table":
            self._show_results("res-table")
        elif btn_id == "res-btn-output":
            self._show_results("res-output")

    def _handle_clear(self) -> None:
        """Clear SQL input with confirmation."""
        sql_area = self.query_one("#adhoc-sql-area", TextArea)
        if not sql_area.text.strip():
            return  # nothing to clear

        from dbqm.ui.modals.confirm import ConfirmModal

        modal = ConfirmModal(
            message="Limpar o conteudo SQL?",
            title="Confirmar limpeza",
        )
        self.app.push_screen(modal, callback=self._on_clear_confirmed)

    def _on_clear_confirmed(self, confirmed: bool | None) -> None:
        """Callback from ConfirmModal for clearing."""
        if not confirmed:
            return
        sql_area = self.query_one("#adhoc-sql-area", TextArea)
        sql_area.clear()
        sql_area.focus()

    def _handle_execute(self) -> None:
        """Execute the SQL statement."""
        raw_sql = self._get_sql()
        if not raw_sql:
            self.notify("Nenhum SQL informado.", severity="warning")
            return

        conn = self._get_selected_conn()
        if not conn:
            return

        sql_type = classify_sql(raw_sql)
        if sql_type == "UNKNOWN":
            self.notify(
                "Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE, DELETE, "
                "DDL ou blocos PL/SQL (BEGIN/DECLARE, EXEC).",
                severity="error",
            )
            return

        self._sql_type = sql_type
        self._current_conn = conn
        self._current_sql = raw_sql
        self._capture_output = self._dbms_output_enabled()
        self._table_name = self._extract_table_name(raw_sql, sql_type)

        # Check for existing bind params
        existing_params = detect_params(raw_sql)
        if existing_params:
            self._push_param_modal_for_execution(existing_params)
        else:
            self._execute_sql(raw_sql, conn, {})

    def _extract_table_name(self, sql: str, sql_type: str) -> str:
        """Extract table/object name from SQL."""
        if sql_type == "SELECT":
            parsed = parse_sql(sql)
            return parsed.get("table", "")
        elif sql_type == "DDL":
            # Extract object name from DDL (CREATE/ALTER/DROP ... TYPE NAME)
            m = re.search(
                r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?|ALTER\s+|DROP\s+)"
                r"(?:PACKAGE\s+BODY|PACKAGE|TABLE|VIEW|PROCEDURE|FUNCTION|TRIGGER|"
                r"SEQUENCE|TYPE\s+BODY|TYPE|INDEX|SYNONYM)\s+(?:\w+\.)?(\w+)",
                sql, re.IGNORECASE,
            )
            return m.group(1) if m else ""
        else:
            tbl_match = re.search(
                r"(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM|DELETE)\s+(\S+)",
                sql, re.IGNORECASE,
            )
            return tbl_match.group(1) if tbl_match else ""

    def _push_param_modal_for_execution(self, param_names: list[str]) -> None:
        """Push ParamModal for detected parameters."""
        from dbqm.ui.modals.param_input import ParamModal

        params_dicts = [
            {"name": p, "description": "", "default": ""}
            for p in param_names
        ]
        modal = ParamModal(
            query_name="SQL Avulso",
            params=params_dicts,
            last_values=self._current_params,
        )
        self.app.push_screen(modal, callback=self._on_execute_params_submitted)

    def _on_execute_params_submitted(self, result: dict[str, str] | None) -> None:
        """Callback from ParamModal for execution."""
        if result is None:
            return
        self._current_params = result
        self._execute_sql(self._current_sql, self._current_conn, result)

    def _execute_sql(self, sql: str, conn, params: dict[str, str]) -> None:
        """Start SQL execution in a worker thread."""
        self._current_params = params
        self.query_one(ProgressIndicator).start(
            f"Executando em [bold]{conn.name}[/]..."
        )
        self._run_sql(sql, conn, params)

    @work(thread=True)
    def _run_sql(self, sql: str, conn, params: dict[str, str]) -> None:
        """Execute SQL in a background thread."""
        try:
            result = execute_adhoc(sql, conn, params, capture_output=self._capture_output)
            self.app.call_from_thread(self._on_sql_result, result)
        except Exception as e:
            self.app.call_from_thread(self._show_error, str(e))

    def _show_error(self, msg: str) -> None:
        """Show error notification and stop progress indicator."""
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro: {msg}", severity="error", timeout=8)

    def _on_sql_result(self, result) -> None:
        """Handle SQL result back on the main thread."""
        self.query_one(ProgressIndicator).stop()

        # Unpack DML tuple
        db_connection = None
        if isinstance(result, tuple):
            adhoc_result, db_connection = result
        else:
            adhoc_result = result

        if not adhoc_result.success:
            self.notify(f"Erro: {adhoc_result.error}", severity="error", timeout=8)
            return

        self._current_adhoc_result = adhoc_result
        self._db_connection = db_connection
        self._last_exec_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Log execution
        self._log_audit(adhoc_result)

        # The SQL viewer is only for the "Gerar SQL" flow — hide it on execute.
        self.query_one("#adhoc-sql-viewer").display = False

        if self._sql_type == "SELECT":
            self._show_select_result(adhoc_result)
        elif self._sql_type == "DDL":
            self._show_ddl_result(adhoc_result)
        elif self._sql_type == "PLSQL":
            self._show_plsql_result(adhoc_result)
        else:
            self._show_dml_result(adhoc_result, db_connection)

        self._update_dbms_panel(adhoc_result)

        # Drive the results sub-toggle: PL/SQL and DBMS-output executions land
        # on the Output view; a plain SELECT lands on the Tabela view.
        show_output = self._capture_output or self._sql_type == "PLSQL"
        if self._sql_type == "SELECT" and not show_output:
            self._show_results("res-table")
        else:
            self._show_results("res-output")

    def _update_dbms_panel(self, result: AdhocResult) -> None:
        """Show/hide the DBMS_OUTPUT panel and load its captured lines."""
        panel = self.query_one("#adhoc-dbms-panel")
        # PL/SQL always surfaces its output; other types only when opted-in.
        show = self._capture_output or self._sql_type == "PLSQL"
        if not show:
            panel.display = False
            return

        self._dbms_output_lines = list(result.output_lines)
        view = self.query_one("#adhoc-dbms-view", TextArea)
        if result.output_lines:
            view.text = "\n".join(result.output_lines)
        else:
            view.text = "(sem saida DBMS_OUTPUT)"
        panel.display = True

    def _log_audit(self, result: AdhocResult) -> None:
        """Log execution to audit."""
        try:
            from dbqm.core.audit import log_execution
            if self._sql_type == "SELECT":
                log_execution(
                    "adhoc_select",
                    self._table_name or "adhoc",
                    result.connection_name,
                    self._current_params,
                    result.row_count,
                    result.success,
                )
            else:
                log_execution(
                    f"adhoc_{self._sql_type.lower()}",
                    "adhoc",
                    result.connection_name,
                    self._current_params,
                    result.rows_affected,
                    result.success,
                )
        except Exception:
            pass

    def _show_select_result(self, result: AdhocResult) -> None:
        """Display SELECT results in the ResultTable."""
        qr = QueryResult(
            query_name="SQL Avulso",
            connection_name=result.connection_name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        )
        self._current_result = qr

        # Show info bar
        info = self.query_one("#adhoc-result-info", Static)
        info.update(
            f"[bold]SQL Avulso[/] | {result.connection_name} | "
            f"{result.row_count} registros | {result.elapsed:.2f}s"
        )
        info.display = True

        # Show result table
        result_table = self.query_one("#res-table", ResultTable)
        result_table.display = True
        result_table.load_result(qr)

        # Hide DML-specific elements
        self.query_one("#adhoc-dml-result").display = False
        self.query_one("#adhoc-sql-viewer").display = False

        # Set up action bar
        self._set_select_actions(result_table)

    def _set_select_actions(self, result_table: ResultTable) -> None:
        """Configure the action bar for SELECT results."""
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return

        actions = [
            Action("Vertical", "V", "toggle_vertical"),
            Action("Exportar", "E", "export"),
            Action("Reexecutar", "R", "reexecute"),
        ]
        if result_table.total_pages > 1:
            actions.append(Action("Pag.Ant", "PgUp", "prev_page"))
            actions.append(Action("Prox.Pag", "PgDn", "next_page"))
            actions.append(Action(result_table.page_info, "", "page_info"))

        action_bar.set_actions(actions)

    def _show_dml_result(self, result: AdhocResult, db_connection) -> None:
        """Display DML result with commit/rollback options."""
        # Hide SELECT elements
        self.query_one("#adhoc-result-info").display = False
        self.query_one("#res-table").display = False
        self.query_one("#adhoc-sql-viewer").display = False

        # Show DML result
        dml_static = self.query_one("#adhoc-dml-result", Static)
        dml_static.display = True
        dml_static.update(
            f"[bold]{result.rows_affected}[/] linha(s) afetada(s) ({result.elapsed:.2f}s)"
        )

        if db_connection:
            # Show commit/rollback in action bar
            try:
                action_bar = self.app.query_one(ActionBar)
                action_bar.set_actions([
                    Action("COMMIT", "C", "dml_commit"),
                    Action("ROLLBACK", "R", "dml_rollback"),
                ])
            except Exception:
                pass
        else:
            self.notify("Conexao nao disponivel para commit/rollback.", severity="warning")

    def _show_ddl_result(self, result: AdhocResult) -> None:
        """Display DDL execution result with compilation errors if any."""
        # Hide SELECT elements
        self.query_one("#adhoc-result-info").display = False
        self.query_one("#res-table").display = False
        self.query_one("#adhoc-sql-viewer").display = False

        # Show result in DML static area
        dml_static = self.query_one("#adhoc-dml-result", Static)
        dml_static.display = True

        if result.success:
            dml_static.update(
                f"[bold]DDL executado com sucesso[/] ({result.elapsed:.2f}s)"
            )
        else:
            errors = result.error or "Erro desconhecido"
            dml_static.update(
                f"[bold $op-falha]DDL executado com erros de compilacao[/] ({result.elapsed:.2f}s)\n\n"
                f"[$op-falha]{errors}[/]"
            )

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([
                Action("Reexecutar", "R", "reexecute"),
            ])
        except Exception:
            pass

    def _show_plsql_result(self, result: AdhocResult) -> None:
        """Display PL/SQL block result with captured DBMS_OUTPUT lines."""
        # Hide SELECT elements
        self.query_one("#adhoc-result-info").display = False
        self.query_one("#res-table").display = False
        self.query_one("#adhoc-sql-viewer").display = False

        dml_static = self.query_one("#adhoc-dml-result", Static)
        dml_static.display = True
        dml_static.update(_format_plsql_message(result))

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([
                Action("Reexecutar", "R", "reexecute"),
            ])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # DBMS_OUTPUT panel actions
    # ------------------------------------------------------------------

    def _handle_dbms_save(self) -> None:
        """Save the execution evidence (SQL + date/time + DBMS_OUTPUT) to a .txt file."""
        result = self._current_adhoc_result
        if result is None:
            self.notify("Nada para salvar.", severity="warning")
            return
        from dbqm.core.exporter import export_dbms_output

        try:
            label = self._table_name or "adhoc"
            path = export_dbms_output(
                result, self._current_sql, self._last_exec_at,
                label, self._current_params,
            )
            self.notify(f"Evidencia salva: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao salvar: {e}", severity="error")

    def _copy_dbms_output(self) -> None:
        """Copy the execution evidence (SQL + date/time + DBMS_OUTPUT) to the clipboard."""
        result = self._current_adhoc_result
        if result is None:
            self.notify("Nada para copiar.", severity="warning")
            return
        from dbqm.core.exporter import format_dbms_evidence

        text = format_dbms_evidence(result, self._current_sql, self._last_exec_at)
        try:
            import subprocess
            process = subprocess.Popen(["clip"], stdin=subprocess.PIPE)
            process.communicate(text.encode("utf-8"))
            self.notify("Evidencia copiada para a area de transferencia!", timeout=3)
        except Exception:
            self.notify("Erro ao copiar. Selecione e copie manualmente.", severity="warning")

    # ------------------------------------------------------------------
    # Generate SQL
    # ------------------------------------------------------------------

    def _handle_generate(self) -> None:
        """Generate final SQL with parameters replaced."""
        raw_sql = self._get_sql()
        if not raw_sql:
            self.notify("Nenhum SQL informado.", severity="warning")
            return

        existing_params = detect_params(raw_sql)
        if existing_params:
            from dbqm.ui.modals.param_input import ParamModal

            params_dicts = [
                {"name": p, "description": "", "default": ""}
                for p in existing_params
            ]
            modal = ParamModal(
                query_name="Gerar SQL",
                params=params_dicts,
                last_values=self._current_params,
            )
            self.app.push_screen(modal, callback=self._on_generate_params_submitted)
        else:
            # No params — just show the SQL as-is
            self._show_generated_sql(raw_sql, {})

    def _on_generate_params_submitted(self, result: dict[str, str] | None) -> None:
        if result is None:
            return
        self._current_params = result
        raw_sql = self._get_sql()
        self._show_generated_sql(raw_sql, result)

    def _show_generated_sql(self, sql: str, params: dict[str, str]) -> None:
        """Show generated SQL in SqlViewer, inside the Output results view."""
        final_sql = generate_sql_text(sql, params) if params else sql

        # Hide SELECT/DML elements; surface the generated SQL in the output pane.
        self.query_one("#adhoc-result-info").display = False
        self.query_one("#res-table").display = False
        self.query_one("#adhoc-dml-result").display = False
        self.query_one("#adhoc-dbms-panel").display = False

        # Show SQL viewer
        sql_viewer = self.query_one("#adhoc-sql-viewer", SqlViewer)
        sql_viewer.display = True
        sql_viewer.set_sql(final_sql)
        self._show_results("res-output")

        # Action bar with export
        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([
                Action("Exportar SQL", "E", "export_sql"),
            ])
        except Exception:
            pass

        self._generated_sql = final_sql

    # ------------------------------------------------------------------
    # Save as query
    # ------------------------------------------------------------------

    def _handle_save(self) -> None:
        """Save the ad-hoc SQL as a regular query."""
        raw_sql = self._get_sql()
        if not raw_sql:
            self.notify("Nenhum SQL informado.", severity="warning")
            return

        conn = self._get_selected_conn()
        if not conn:
            return

        from dbqm.ui.modals.text_input import TextInputModal

        sql_type = classify_sql(raw_sql)
        table_name = self._extract_table_name(raw_sql, sql_type) if sql_type != "UNKNOWN" else ""
        suggested = ""
        if table_name:
            clean_table = table_name.strip('"').strip("[]").split(".")[-1]
            suggested = f"{clean_table} ({conn.name})"

        modal = TextInputModal(
            title="Salvar como consulta",
            message="Nome da consulta:",
            default=suggested,
        )
        self.app.push_screen(modal, callback=self._on_save_name_submitted)

    def _on_save_name_submitted(self, name: str | None) -> None:
        """Callback from TextInputModal for saving."""
        if not name:
            return

        from dbqm.models.query import Query, QueryParam, load_queries, save_queries

        existing = load_queries()
        if any(q.name == name for q in existing):
            self.notify(f'Consulta "{name}" ja existe.', severity="error")
            return

        raw_sql = self._get_sql()
        sql_type = classify_sql(raw_sql)
        conn = self._get_selected_conn()
        if not conn:
            return

        table_name = self._extract_table_name(raw_sql, sql_type) if sql_type != "UNKNOWN" else ""

        columns = []
        if sql_type == "SELECT":
            parsed = parse_sql(raw_sql)
            columns = parsed.get("columns", [])

        # Detect params for the saved query
        param_names = detect_params(raw_sql)
        params = [QueryParam(name=p, description="", default="") for p in param_names]

        query = Query(
            name=name,
            connection=conn.name,
            sql=raw_sql.strip().rstrip(";"),
            table=table_name,
            params=params,
            columns=columns,
        )

        existing.append(query)
        save_queries(existing)
        self.notify(f'Consulta "{name}" salva!', timeout=5)

    # ------------------------------------------------------------------
    # DML commit/rollback
    # ------------------------------------------------------------------

    def _handle_commit(self) -> None:
        if self._db_connection:
            try:
                self._db_connection.commit()
                self._db_connection.close()
            except Exception as e:
                self.notify(f"Erro no commit: {e}", severity="error")
                return
            finally:
                self._db_connection = None
            self.notify("COMMIT executado. Alteracoes efetivadas.", timeout=5)
            self._clear_action_bar()

    def _handle_rollback(self) -> None:
        if self._db_connection:
            try:
                self._db_connection.rollback()
                self._db_connection.close()
            except Exception as e:
                self.notify(f"Erro no rollback: {e}", severity="error")
                return
            finally:
                self._db_connection = None
            self.notify("ROLLBACK executado. Alteracoes desfeitas.", severity="warning", timeout=5)
            self._clear_action_bar()

    def _clear_action_bar(self) -> None:
        try:
            self.app.query_one(ActionBar).set_actions([])
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "toggle_vertical":
            result_table = self.query_one("#res-table", ResultTable)
            result_table.toggle_vertical()
        elif action == "export":
            self._handle_export()
        elif action == "reexecute":
            self._handle_reexecute()
        elif action == "prev_page":
            result_table = self.query_one("#res-table", ResultTable)
            result_table.prev_page()
            self._set_select_actions(result_table)
        elif action == "next_page":
            result_table = self.query_one("#res-table", ResultTable)
            result_table.next_page()
            self._set_select_actions(result_table)
        elif action == "export_sql":
            self._handle_export_sql()
        elif action == "dml_commit":
            self._handle_commit()
        elif action == "dml_rollback":
            self._handle_rollback()

    def _handle_export(self) -> None:
        from dbqm.ui.modals.export_picker import request_export

        request_export(self.app, include_png=False, callback=self._on_export_format_selected)

    def _on_export_format_selected(self, fmt: str | None) -> None:
        if fmt is None or self._current_result is None:
            return

        from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt

        table = self._table_name
        params = self._current_params

        try:
            if fmt == "csv":
                path = export_query_csv(self._current_result, table=table, params=params)
            elif fmt == "json":
                path = export_query_json(self._current_result, table=table, params=params)
            elif fmt == "txt":
                path = export_query_txt(self._current_result, table=table, params=params)
            else:
                self.notify(f"Formato '{fmt}' nao suportado.", severity="warning")
                return
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    def _handle_export_sql(self) -> None:
        """Export the generated SQL to a .sql file."""
        from dbqm.core.exporter import export_sql_file

        try:
            label = self._table_name if self._table_name else "adhoc"
            path = export_sql_file(self._generated_sql, label, self._current_params)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    def _handle_reexecute(self) -> None:
        """Re-execute with new/same parameters."""
        # Roll back / close any open DML transaction from the previous run
        # before starting a fresh execution.
        self._cleanup_db_connection()
        self._handle_execute()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def _cleanup_db_connection(self) -> None:
        """Roll back and close any open DML connection (uncommitted work)."""
        if self._db_connection:
            try:
                self._db_connection.rollback()
                self._db_connection.close()
            except Exception:
                pass
            self._db_connection = None

    def on_unmount(self) -> None:
        """Ensure no uncommitted DML transaction leaks when leaving the screen."""
        self._cleanup_db_connection()
