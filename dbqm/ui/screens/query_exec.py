"""Query execution screen — select, parameterize, execute, and view results."""
from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll, Vertical
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
        height: 3;
        width: 1fr;
        padding: 0 1;
        background: $surface;
        scrollbar-size-horizontal: 1;
    }
    QueryExecScreen #folder-bar Button {
        min-width: 6;
        margin: 0 1 0 0;
    }
    QueryExecScreen #folder-hint {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: dim italic;
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
        self._raw_rows: list[list] | None = None  # rows before column maps
        self._showing_mapped: bool = True
        self._folder_map: dict[str, str] = {}
        self._folder_buttons: list[Button] = []
        self._active_folder_idx: int = 0

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
            folder_bar = HorizontalScroll(id="folder-bar")
            selection.mount(folder_bar)
            # "Todas" button
            btn_todas = Button("Todas", id="folder-todas", variant="primary")
            folder_bar.mount(btn_todas)
            self._folder_buttons = [btn_todas]
            for folder in folders:
                safe_id = sanitize_id(folder)
                self._folder_map[safe_id] = folder
                btn = Button(folder, id=f"folder-{safe_id}", variant="default")
                folder_bar.mount(btn)
                self._folder_buttons.append(btn)
            has_no_folder = any(not q.folder for q in queries)
            if has_no_folder:
                btn_sem = Button("Sem pasta", id="folder-sem-pasta", variant="default")
                folder_bar.mount(btn_sem)
                self._folder_buttons.append(btn_sem)
            # Hint for keyboard navigation
            selection.mount(Static("[dim]← → alternar pastas[/dim]", id="folder-hint", markup=True))
            self._active_folder_idx = 0

        selection.mount(ql)
        ql.load_queries(queries)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle folder filter button presses."""
        btn_id = event.button.id or ""
        if not btn_id.startswith("folder-"):
            return

        # Sync index
        for i, b in enumerate(self._folder_buttons):
            if b is event.button:
                self._active_folder_idx = i
                break

        self._activate_folder_button(event.button)

    # ------------------------------------------------------------------
    # Folder keyboard navigation (← →)
    # ------------------------------------------------------------------

    def key_left(self) -> None:
        """Switch to previous folder."""
        if not self._folder_buttons:
            return
        self._active_folder_idx = max(0, self._active_folder_idx - 1)
        self._activate_folder_button(self._folder_buttons[self._active_folder_idx])

    def key_right(self) -> None:
        """Switch to next folder."""
        if not self._folder_buttons:
            return
        self._active_folder_idx = min(len(self._folder_buttons) - 1, self._active_folder_idx + 1)
        self._activate_folder_button(self._folder_buttons[self._active_folder_idx])

    def _activate_folder_button(self, btn: Button) -> None:
        """Simulate clicking a folder button."""
        for b in self._folder_buttons:
            b.variant = "default"
        btn.variant = "primary"
        # Trigger the filter
        btn_id = btn.id or ""
        safe_id = btn_id.removeprefix("folder-")
        ql = self.query_one("#ql-main", QueryListWidget)
        if safe_id == "todas":
            ql.load_queries(self._all_queries)
        elif safe_id == "sem-pasta":
            ql.load_queries([q for q in self._all_queries if not q.folder])
        else:
            folder_label = self._folder_map.get(safe_id, "")
            ql.load_queries([q for q in self._all_queries if q.folder == folder_label])
        # Keep focus on the list
        ql.focus()

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
        import copy

        try:
            result = execute_query(query, conn, params)

            # Save raw rows before applying column maps
            raw_rows = copy.deepcopy(result.rows) if result.success and result.rows and query.column_maps else None

            # Apply column maps (DE-PARA)
            if result.success and result.rows:
                query.apply_column_maps(result.rows, result.columns)

            self.app.call_from_thread(self._on_result, query, conn, params, result, raw_rows)
        except Exception as e:
            self.app.call_from_thread(self._show_error, str(e))

    def _show_error(self, msg: str) -> None:
        """Show error notification and stop progress indicator."""
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro: {msg}", severity="error", timeout=8)

    def _on_result(self, query, conn, params: dict[str, str], result: QueryResult, raw_rows: list[list] | None = None) -> None:
        """Handle query result back on the main thread."""
        self.query_one(ProgressIndicator).stop()

        if not result.success:
            self.notify(f"Erro: {result.error}", severity="error", timeout=8)
            return

        self._current_result = result
        self._raw_rows = raw_rows
        self._showing_mapped = True

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
        ]
        if self._raw_rows is not None:
            label = "Original" if self._showing_mapped else "De-Para"
            actions.append(Action(label, "M", "toggle_mapping"))
        actions.extend([
            Action("Exportar", "E", "export"),
            Action("Reexecutar", "R", "reexecute"),
        ])
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
        elif action == "toggle_mapping":
            self._handle_toggle_mapping()
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

    def _handle_toggle_mapping(self) -> None:
        """Toggle between mapped (de-para) and original result view."""
        import copy
        if self._current_result is None or self._raw_rows is None:
            return

        result_table = self.query_one("#result-table", ResultTable)

        if self._showing_mapped:
            # Switch to original: swap rows with raw copy
            self._current_result.rows = copy.deepcopy(self._raw_rows)
            self._showing_mapped = False
            self.notify("Exibindo valores originais", timeout=2)
        else:
            # Switch to mapped: re-apply column maps
            self._current_result.rows = copy.deepcopy(self._raw_rows)
            self._current_query.apply_column_maps(self._current_result.rows, self._current_result.columns)
            self._showing_mapped = True
            self.notify("Exibindo valores mapeados (de-para)", timeout=2)

        result_table.load_result(self._current_result)
        self._set_result_actions(result_table)

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
        self._raw_rows = None
        self._showing_mapped = True

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([])
        except Exception:
            pass

        # Restore focus to query list
        try:
            from dbqm.ui.widgets.query_list import QueryListWidget
            self.query_one("#ql-main", QueryListWidget).focus()
        except Exception:
            pass
