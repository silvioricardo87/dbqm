"""Query execution screen — select, parameterize, execute, and view results."""
from __future__ import annotations

from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static
from textual import work

from dbqm.ui.utils import escape_markup, NavSelect, prefixo_comum_de_pastas
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.esqueleto import Esqueleto
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.query_list import ClearFiltersRequested, QueryListWidget, QuerySelected
from dbqm.ui.widgets.result_table import ResultTable

from dbqm.core.query_engine import QueryResult


class QueryExecScreen(Vertical):
    """Screen widget for executing saved queries.

    Phase 1 — query selection (folder select + QueryListWidget).
    Phase 2 — results (info bar + ResultTable).
    """

    DEFAULT_CSS = """
    QueryExecScreen {
        height: 1fr;
    }
    QueryExecScreen #selection-phase {
        height: 1fr;
        margin: 1 2 0 2;
    }
    QueryExecScreen #results-phase {
        height: 1fr;
        margin: 1 2 0 2;
    }
    QueryExecScreen #result-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    QueryExecScreen #empty-message {
        height: 1fr;
    }
    QueryExecScreen #result-skeleton {
        display: none;
    }
    QueryExecScreen #folder-select {
        width: 1fr;
        margin: 0 1 1 1;
    }
    QueryExecScreen #qe-filter-bar {
        height: auto;
        padding: 1 1 0 1;
        background: $surface;
    }
    QueryExecScreen #qe-filter-bar Input {
        width: 1fr;
    }
    QueryExecScreen #qe-filter-bar Select {
        width: 34;
        margin: 0 0 0 1;
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
        # "" = Todas, None = Sem pasta, qualquer outro valor = nome da pasta.
        # Espelha o valor do `#folder-select`; None e distinto do sentinela
        # de "em branco" do proprio Select (`Select.NULL`), entao nao ha
        # ambiguidade entre "nenhuma pasta selecionada" (nao ocorre aqui,
        # allow_blank=False) e "pasta = sem pasta".
        self._active_folder: str | None = ""
        self._has_folders: bool = False

    def compose(self) -> ComposeResult:
        # Selection phase
        with Panel("📋  CONSULTAS", id="selection-phase"):
            yield EmptyState(
                o_que="Consultas",
                porque="Consultas salvas ficam aqui e podem ser reexecutadas quando voce quiser",
                acao_rotulo="Criar consulta",
                acao_id="criar-consulta-coleta",
                id="empty-message",
            )
        # Progress indicator (hidden by default)
        yield ProgressIndicator()
        # Results phase (hidden initially)
        with Panel("📊  RESULTADO", id="results-phase"):
            yield Static("", id="result-info")
            # A forma da tabela que vem, nao um rodopio: reserva o espaco
            # certo para a primeira execucao, hidden ate `_execute` mostrar.
            # 9 e a mediana das 68 consultas salvas do mantenedor (min 1, max
            # 36), levantada na fase 1 deste plano — nao reproduzivel a
            # partir de config/queries.json deste repositorio, que e outro
            # conjunto, menor. E o melhor palpite disponivel (bem melhor que
            # os 4 arbitrarios), nao uma verdade do dominio: um esqueleto com
            # a forma errada causa o salto de layout que ele existe para
            # impedir.
            yield Esqueleto(linhas=8, colunas=9, id="result-skeleton")
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
        # `.corpo` e nao o painel: montagem em runtime nao passa pelo
        # roteamento de `compose_add_child` e cairia fora da moldura.
        selection = self.query_one("#selection-phase", Panel).corpo
        empty_msg = self.query_one("#empty-message", EmptyState)

        if not queries:
            empty_msg.display = True
            return

        empty_msg.display = False
        self._queries = queries
        self._all_queries = queries

        # Filter bar — text (name/description) + connection select
        conn_options = [
            (c, c) for c in sorted({q.connection for q in queries if q.connection})
        ]
        selection.mount(
            Horizontal(
                Input(
                    # Sem as reticencias: com a moldura, este `1fr` mede 35
                    # colunas em 80 (eram 43) e o texto saia cortado como
                    # "...descricao..", que parece defeito. 29 caracteres
                    # cabem inteiros na largura mais estreita que o
                    # produto suporta.
                    placeholder="Filtrar por nome ou descricao",
                    id="qe-filter-text",
                ),
                NavSelect(conn_options, prompt="Todas as conexoes", id="qe-filter-conn"),
                id="qe-filter-bar",
            )
        )

        # Determine folders — cardinalidade variavel (o mantenedor real tem
        # 16), entao a navegacao e um Select com a contagem por opcao, nao
        # abas: 16 botoes numa HorizontalScroll obrigava a rolar
        # lateralmente pra achar uma pasta, e a maioria de cada botao era o
        # mesmo prefixo repetido.
        from collections import Counter

        contagem_pastas = Counter(q.folder for q in queries if q.folder)
        folders = sorted(contagem_pastas)
        self._has_folders = bool(folders)

        ql = QueryListWidget(id="ql-main")

        if folders:
            prefixo = prefixo_comum_de_pastas(folders)
            options = [(f"Todas ({len(queries)})", "")]
            for folder in folders:
                rotulo = folder[len(prefixo):] if prefixo and folder.startswith(prefixo) else folder
                options.append((f"{rotulo} ({contagem_pastas[folder]})", folder))
            sem_pasta = sum(1 for q in queries if not q.folder)
            if sem_pasta:
                options.append((f"Sem pasta ({sem_pasta})", None))
            selection.mount(
                NavSelect(options, allow_blank=False, id="folder-select")
            )
            self._active_folder = ""

        selection.mount(ql)
        ql.load_queries(queries)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle the empty-state action."""
        btn_id = event.button.id or ""
        if btn_id == "criar-consulta-coleta":
            # Queries are created from the Coleta tab ("Salvar como
            # consulta" there), not from this screen — guarded because
            # QueryExecScreen is also mounted standalone in tests, where
            # self.app has no action_switch_tab (that lives on DBQMApp
            # only).
            switch = getattr(self.app, "action_switch_tab", None)
            if callable(switch):
                switch("tab-coleta")
            return

    # ------------------------------------------------------------------
    # Text + connection filtering
    # ------------------------------------------------------------------

    def _folder_subset(self) -> list:
        """Queries within the currently selected folder."""
        valor = self._active_folder
        if valor is None:
            return [q for q in self._all_queries if not q.folder]
        if valor:
            return [q for q in self._all_queries if q.folder == valor]
        return list(self._all_queries)

    def _apply_filters(self) -> None:
        """Recompute the visible list from folder + text + connection filters."""
        from dbqm.models.query import filter_queries

        try:
            ql = self.query_one("#ql-main", QueryListWidget)
        except Exception:
            return  # list not mounted yet (early Select.Changed on mount)

        text = self.query_one("#qe-filter-text", Input).value
        conn_val = self.query_one("#qe-filter-conn", Select).value
        conn = conn_val if isinstance(conn_val, str) else ""

        filtered = filter_queries(self._folder_subset(), text=text, connection=conn)
        ql.load_queries(filtered)

    def on_input_changed(self, event: Input.Changed) -> None:
        """React to the text filter as the user types."""
        if event.input.id == "qe-filter-text":
            self._apply_filters()

    def on_select_changed(self, event: Select.Changed) -> None:
        """React to the connection and folder filter selections."""
        if event.select.id == "qe-filter-conn":
            self._apply_filters()
        elif event.select.id == "folder-select":
            self._active_folder = event.value
            self._apply_filters()
            # Keep focus on the list, same as the old folder tabs did.
            try:
                self.query_one("#ql-main", QueryListWidget).focus()
            except Exception:
                pass

    def on_clear_filters_requested(self, message: ClearFiltersRequested) -> None:
        """The QueryListWidget's filtered-to-nothing EmptyState asked to
        clear the filters that live up here (folder select, connection,
        free-text search) — the widget already cleared its own inline
        search box."""
        self._active_folder = ""
        if self._has_folders:
            try:
                self.query_one("#folder-select", Select).value = ""
            except Exception:
                pass
        try:
            self.query_one("#qe-filter-text", Input).value = ""
        except Exception:
            pass
        try:
            self.query_one("#qe-filter-conn", Select).clear()
        except Exception:
            pass
        self._apply_filters()

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
        message = (
            f"Executando [bold]{escape_markup(query.name)}[/] em "
            f"[bold]{escape_markup(conn.name)}[/]..."
        )
        if self._current_result is None:
            # First load into the (still empty) results area: show the
            # shape of the table that is coming instead of a spinner, so
            # the layout does not jump when the real result lands.
            self.query_one("#selection-phase").display = False
            self.query_one("#results-phase").display = True
            self.query_one("#result-table", ResultTable).display = False
            self.query_one("#result-skeleton", Esqueleto).display = True
            self.query_one("#result-info", Static).update(message)
        else:
            # Reexecuting: a result is already on screen. Keep it visible
            # and use the message indicator, not the skeleton — replacing
            # good data with placeholder blocks would be a worse jump than
            # the one the skeleton exists to avoid.
            self.query_one(ProgressIndicator).start(message)
        self._run_query(query, conn, params)

    def _abort_first_load_if_pending(self) -> None:
        """Undo the skeleton phase-switch from `_execute` when the FIRST
        execution never produced a result — otherwise a failed first
        execution strands the screen on an empty results phase with no way
        back to the query list."""
        if self._current_result is not None:
            return
        self.query_one("#selection-phase").display = True
        self.query_one("#results-phase").display = False
        self.query_one("#result-skeleton", Esqueleto).display = False
        self.query_one("#result-table", ResultTable).display = True

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
        self._abort_first_load_if_pending()
        self.notify(f"Erro: {msg}", severity="error", timeout=8)

    def _on_result(self, query, conn, params: dict[str, str], result: QueryResult, raw_rows: list[list] | None = None) -> None:
        """Handle query result back on the main thread."""
        self.query_one(ProgressIndicator).stop()

        if not result.success:
            self._abort_first_load_if_pending()
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

        # Real data arrived: the skeleton (if it was up for a first load)
        # gives way to the table it stood in for.
        self.query_one("#result-skeleton", Esqueleto).display = False
        self.query_one("#result-table", ResultTable).display = True

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
        from dbqm.ui.modals.export_picker import request_export

        request_export(self.app, include_png=False, callback=self._on_export_format_selected)

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
        self.query_one("#result-skeleton", Esqueleto).display = False
        self.query_one("#result-table", ResultTable).display = True
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
