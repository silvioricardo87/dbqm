"""Ad-hoc SQL execution screen — type SQL, execute, view results."""
from __future__ import annotations

import re

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Select, Static, TextArea
from dbqm.ui.utils import NavSelect
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
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


class AdhocScreen(Vertical):
    """Screen widget for executing ad-hoc SQL statements.

    Phase 1 — SQL input with connection selector and action buttons.
    Phase 2 — results (ResultTable for SELECT, info for DML).
    """

    DEFAULT_CSS = """
    AdhocScreen {
        height: 1fr;
    }
    AdhocScreen #adhoc-input-phase {
        height: 1fr;
    }
    AdhocScreen #adhoc-conn-bar {
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    AdhocScreen #adhoc-conn-bar Select {
        width: 1fr;
    }
    AdhocScreen #adhoc-sql-area {
        height: 1fr;
        margin: 0 1;
    }
    AdhocScreen #adhoc-btn-bar {
        height: auto;
        padding: 1;
        align: center middle;
    }
    AdhocScreen #adhoc-btn-bar Button {
        margin: 0 1;
    }
    AdhocScreen #adhoc-results-phase {
        height: 1fr;
    }
    AdhocScreen #adhoc-result-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    AdhocScreen #adhoc-dml-result {
        height: auto;
        padding: 1 2;
        content-align: center middle;
        text-align: center;
    }
    AdhocScreen #adhoc-sql-viewer-area {
        height: 1fr;
        padding: 0 1;
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

    def compose(self) -> ComposeResult:
        # Input phase
        with Vertical(id="adhoc-input-phase"):
            with Horizontal(id="adhoc-conn-bar"):
                yield NavSelect([], prompt="Selecione a conexao", id="adhoc-conn-select")
            yield TextArea("", language="sql", id="adhoc-sql-area")
            with Horizontal(id="adhoc-btn-bar"):
                yield Button("Executar", variant="primary", id="adhoc-execute")
                yield Button("Gerar SQL", variant="default", id="adhoc-generate")
                yield Button("Salvar como consulta", variant="default", id="adhoc-save")

        # Progress indicator
        yield ProgressIndicator()

        # Results phase (hidden initially)
        with Vertical(id="adhoc-results-phase"):
            yield Static("", id="adhoc-result-info")
            yield ResultTable(id="adhoc-result-table")
            yield Static("", id="adhoc-dml-result")
            yield SqlViewer("", id="adhoc-sql-viewer")

    def on_mount(self) -> None:
        self.query_one("#adhoc-results-phase").display = False
        self.query_one("#adhoc-dml-result").display = False
        self.query_one("#adhoc-sql-viewer").display = False
        self._load_connections()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#adhoc-sql-area", TextArea).focus()
        except Exception:
            pass

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
        elif btn_id == "adhoc-generate":
            self._handle_generate()
        elif btn_id == "adhoc-save":
            self._handle_save()
        elif btn_id == "adhoc-commit":
            self._handle_commit()
        elif btn_id == "adhoc-rollback":
            self._handle_rollback()

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
                "Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE ou DELETE.",
                severity="error",
            )
            return

        self._sql_type = sql_type
        self._current_conn = conn
        self._current_sql = raw_sql
        self._table_name = self._extract_table_name(raw_sql, sql_type)

        # Check for existing bind params
        existing_params = detect_params(raw_sql)
        if existing_params:
            self._push_param_modal_for_execution(existing_params)
        else:
            self._execute_sql(raw_sql, conn, {})

    def _extract_table_name(self, sql: str, sql_type: str) -> str:
        """Extract table name from SQL."""
        if sql_type == "SELECT":
            parsed = parse_sql(sql)
            return parsed.get("table", "")
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
            result = execute_adhoc(sql, conn, params)
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

        # Log execution
        self._log_audit(adhoc_result)

        # Switch to results phase
        self.query_one("#adhoc-input-phase").display = False
        results_phase = self.query_one("#adhoc-results-phase")
        results_phase.display = True

        if self._sql_type == "SELECT":
            self._show_select_result(adhoc_result)
        else:
            self._show_dml_result(adhoc_result, db_connection)

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
        result_table = self.query_one("#adhoc-result-table", ResultTable)
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
        self.query_one("#adhoc-result-table").display = False
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
        """Show generated SQL in SqlViewer."""
        final_sql = generate_sql_text(sql, params) if params else sql

        # Switch to results phase
        self.query_one("#adhoc-input-phase").display = False
        results_phase = self.query_one("#adhoc-results-phase")
        results_phase.display = True

        # Hide SELECT/DML elements
        self.query_one("#adhoc-result-info").display = False
        self.query_one("#adhoc-result-table").display = False
        self.query_one("#adhoc-dml-result").display = False

        # Show SQL viewer
        sql_viewer = self.query_one("#adhoc-sql-viewer", SqlViewer)
        sql_viewer.display = True
        sql_viewer.set_sql(final_sql)

        # Action bar with export
        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([
                Action("Exportar SQL", "E", "export_sql"),
                Action("Voltar", "Esc", "go_back"),
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
            result_table = self.query_one("#adhoc-result-table", ResultTable)
            result_table.toggle_vertical()
        elif action == "export":
            self._handle_export()
        elif action == "reexecute":
            self._handle_reexecute()
        elif action == "prev_page":
            result_table = self.query_one("#adhoc-result-table", ResultTable)
            result_table.prev_page()
            self._set_select_actions(result_table)
        elif action == "next_page":
            result_table = self.query_one("#adhoc-result-table", ResultTable)
            result_table.next_page()
            self._set_select_actions(result_table)
        elif action == "export_sql":
            self._handle_export_sql()
        elif action == "go_back":
            self.go_back_to_input()
        elif action == "dml_commit":
            self._handle_commit()
        elif action == "dml_rollback":
            self._handle_rollback()

    def _handle_export(self) -> None:
        from dbqm.ui.modals.export_picker import ExportPickerModal

        modal = ExportPickerModal(include_png=False)
        self.app.push_screen(modal, callback=self._on_export_format_selected)

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
        self.go_back_to_input()
        self._handle_execute()

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    def go_back_to_input(self) -> None:
        """Return to the SQL input phase."""
        if self._db_connection:
            try:
                self._db_connection.rollback()
                self._db_connection.close()
            except Exception:
                pass
            self._db_connection = None
        self.query_one("#adhoc-input-phase").display = True
        self.query_one("#adhoc-results-phase").display = False
        self._current_result = None
        self._current_adhoc_result = None
        self._clear_action_bar()
