"""Query execution screen — select, parameterize, execute, and view results."""
from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Static
from textual import work

from dbqm.ui.utils import sanitize_id, escape_markup
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.query_list import QueryListWidget, QuerySelected
from dbqm.ui.widgets.result_table import ResultTable

from dbqm.core.query_engine import QueryResult


class QueryExecScreen(Vertical):
    """Screen widget for executing saved queries.

    Phase 1 — query selection (folder tabs + QueryListWidget).
    Phase 2 — results (info bar + ResultTable).
    """

    DEFAULT_CSS = """
    QueryExecScreen {
        height: 1fr;
    }
    QueryExecScreen #selection-phase {
        height: 1fr;
    }
    QueryExecScreen #results-phase {
        height: 1fr;
    }
    QueryExecScreen #result-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    QueryExecScreen #empty-message {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    QueryExecScreen #folder-bar {
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    QueryExecScreen #folder-bar Button {
        min-width: 8;
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
        self._current_query = None
        self._current_conn = None
        self._current_params: dict[str, str] = {}
        self._current_result: QueryResult | None = None
        self._folder_map: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        # Selection phase
        with Vertical(id="selection-phase"):
            yield Static(
                "[dim]Nenhuma consulta configurada[/]",
                id="empty-message",
                markup=True,
            )
        # Progress indicator (hidden by default)
        yield ProgressIndicator()
        # Results phase (hidden initially)
        with Vertical(id="results-phase"):
            yield Static("", id="result-info")
            yield ResultTable(id="result-table")

    def on_mount(self) -> None:
        self.query_one("#results-phase").display = False
        self._load_selection()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        try:
            ql = self.query_one("#ql-main", QueryListWidget)
            ql.focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Phase 1: Query selection
    # ------------------------------------------------------------------

    def _load_selection(self) -> None:
        """Load queries and build the selection UI."""
        from dbqm.models.query import load_queries

        queries = load_queries()
        selection = self.query_one("#selection-phase")
        empty_msg = self.query_one("#empty-message", Static)

        if not queries:
            empty_msg.display = True
            return

        empty_msg.display = False
        self._queries = queries

        # Determine folders
        folders = sorted({q.folder for q in queries if q.folder})

        ql = QueryListWidget(id="ql-main")
        self._all_queries = queries

        if folders:
            folder_bar = Horizontal(id="folder-bar")
            selection.mount(folder_bar)
            # "Todas" button
            folder_bar.mount(
                Button("Todas", id="folder-todas", variant="primary")
            )
            for folder in folders:
                safe_id = sanitize_id(folder)
                self._folder_map[safe_id] = folder
                folder_bar.mount(
                    Button(folder, id=f"folder-{safe_id}", variant="default")
                )
            has_no_folder = any(not q.folder for q in queries)
            if has_no_folder:
                folder_bar.mount(
                    Button("Sem pasta", id="folder-sem-pasta", variant="default")
                )

        selection.mount(ql)
        ql.load_queries(queries)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle folder filter button presses."""
        btn_id = event.button.id or ""
        if not btn_id.startswith("folder-"):
            return

        # Update button variants
        try:
            folder_bar = self.query_one("#folder-bar", Horizontal)
            for btn in folder_bar.query(Button):
                btn.variant = "default"
            event.button.variant = "primary"
        except Exception:
            pass

        # Filter the query list
        safe_id = btn_id.removeprefix("folder-")
        ql = self.query_one("#ql-main", QueryListWidget)

        if safe_id == "todas":
            ql.load_queries(self._all_queries)
        elif safe_id == "sem-pasta":
            ql.load_queries([q for q in self._all_queries if not q.folder])
        else:
            folder_label = self._folder_map.get(safe_id, "")
            ql.load_queries(
                [q for q in self._all_queries if q.folder == folder_label]
            )

    # ------------------------------------------------------------------
    # Query selected → parameterize & execute
    # ------------------------------------------------------------------

    def on_query_selected(self, message: QuerySelected) -> None:
        """Handle query selection from the list."""
        from dbqm.models.query import find_query
        from dbqm.models.connection import find_connection

        query = find_query(message.query_name)
        if query is None:
            self.notify(f"Consulta '{message.query_name}' nao encontrada.", severity="error")
            return

        conn = find_connection(query.connection)
        if conn is None:
            self.notify(
                f"Conexao '{query.connection}' nao encontrada para '{query.name}'.",
                severity="error",
            )
            return

        self._current_query = query
        self._current_conn = conn

        if query.params:
            self._push_param_modal(query)
        else:
            self._execute(query, conn, {})

    def _push_param_modal(self, query, last_values: dict[str, str] | None = None) -> None:
        """Push the parameter input modal."""
        from dbqm.ui.modals.param_input import ParamModal

        params_dicts = [
            {"name": p.name, "description": p.description, "default": p.default}
            for p in query.params
        ]
        modal = ParamModal(
            query_name=query.name,
            params=params_dicts,
            last_values=last_values or self._current_params,
            description=query.description,
        )
        self.app.push_screen(modal, callback=self._on_params_submitted)

    def _on_params_submitted(self, result: dict[str, str] | None) -> None:
        """Callback from ParamModal."""
        if result is None:
            return
        self._execute(self._current_query, self._current_conn, result)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(self, query, conn, params: dict[str, str]) -> None:
        """Start query execution in a worker thread."""
        self._current_params = params
        self.query_one(ProgressIndicator).start(
            f"Executando [bold]{escape_markup(query.name)}[/] em [bold]{escape_markup(conn.name)}[/]..."
        )
        self._run_query(query, conn, params)

    @work(thread=True)
    def _run_query(self, query, conn, params: dict[str, str]) -> None:
        """Execute query in a background thread."""
        from dbqm.core.query_engine import execute_query

        result = execute_query(query, conn, params)

        # Apply column maps (DE-PARA)
        if result.success and result.rows:
            query.apply_column_maps(result.rows, result.columns)

        self.call_from_thread(self._on_result, query, conn, params, result)

    def _on_result(self, query, conn, params: dict[str, str], result: QueryResult) -> None:
        """Handle query result back on the main thread."""
        self.query_one(ProgressIndicator).stop()

        if not result.success:
            self.notify(f"Erro: {result.error}", severity="error", timeout=8)
            return

        self._current_result = result

        # Record history & audit
        self._record_execution(query, conn, params, result)

        # Switch to results phase
        self.query_one("#selection-phase").display = False
        results_phase = self.query_one("#results-phase")
        results_phase.display = True

        # Update info bar
        info = self.query_one("#result-info", Static)
        info.update(
            f"[bold]{query.name}[/] | {conn.name} | "
            f"{result.row_count} registros | {result.elapsed:.2f}s"
        )

        # Load result into table
        result_table = self.query_one("#result-table", ResultTable)
        result_table.load_result(result)

        # Set up action bar
        self._set_result_actions(result_table)

    def _set_result_actions(self, result_table: ResultTable) -> None:
        """Configure the action bar for results view."""
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

    def _record_execution(self, query, conn, params: dict, result: QueryResult) -> None:
        """Record execution in history/audit and update last_executed."""
        try:
            from dbqm.core.history import record_query_execution
            record_query_execution(
                query_name=query.name,
                connection_name=conn.name,
                params=params,
                row_count=result.row_count,
                elapsed=result.elapsed,
                success=result.success,
                error=result.error,
            )
        except Exception:
            pass

        try:
            from dbqm.core.audit import log_execution
            log_execution(
                "query",
                query.name,
                conn.name,
                params,
                result.row_count,
                result.success,
                result.error,
            )
        except Exception:
            pass

        # Update last_executed on the query
        try:
            from dbqm.models.query import load_queries, save_queries
            query.last_executed = datetime.now().isoformat(timespec="seconds")
            all_queries = load_queries()
            for q in all_queries:
                if q.name == query.name:
                    q.last_executed = query.last_executed
                    break
            save_queries(all_queries)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        """Handle action bar selections."""
        action = message.action_id

        if action == "toggle_vertical":
            self._handle_toggle_vertical()
        elif action == "export":
            self._handle_export()
        elif action == "reexecute":
            self._handle_reexecute()
        elif action == "prev_page":
            self._handle_prev_page()
        elif action == "next_page":
            self._handle_next_page()

    def _handle_toggle_vertical(self) -> None:
        result_table = self.query_one("#result-table", ResultTable)
        result_table.toggle_vertical()

    def _handle_export(self) -> None:
        from dbqm.ui.modals.export_picker import ExportPickerModal

        modal = ExportPickerModal(include_png=False)
        self.app.push_screen(modal, callback=self._on_export_format_selected)

    def _on_export_format_selected(self, fmt: str | None) -> None:
        """Callback from ExportPickerModal."""
        if fmt is None or self._current_result is None:
            return

        from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt

        table = self._current_query.table if self._current_query else ""
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

    def _handle_reexecute(self) -> None:
        if self._current_query is None:
            return
        if self._current_query.params:
            self._push_param_modal(self._current_query, last_values=self._current_params)
        else:
            self._execute(self._current_query, self._current_conn, {})

    def _handle_prev_page(self) -> None:
        result_table = self.query_one("#result-table", ResultTable)
        result_table.prev_page()
        self._set_result_actions(result_table)

    def _handle_next_page(self) -> None:
        result_table = self.query_one("#result-table", ResultTable)
        result_table.next_page()
        self._set_result_actions(result_table)

    # ------------------------------------------------------------------
    # Back navigation support
    # ------------------------------------------------------------------

    def go_back_to_selection(self) -> None:
        """Return to the query selection phase."""
        self.query_one("#selection-phase").display = True
        self.query_one("#results-phase").display = False
        self._current_result = None

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([])
        except Exception:
            pass
