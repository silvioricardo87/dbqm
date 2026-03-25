"""Group execution screen — select group, execute queries, compare results."""
from __future__ import annotations

import time
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, HorizontalScroll, Vertical
from textual.message import Message
from textual.widgets import Button, ListItem, ListView, Static
from textual import work

from dbqm.ui.utils import sanitize_id, escape_markup
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.group_result import GroupResultWidget
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.result_table import ResultTable

from dbqm.core.group_engine import GroupResult


# ---------------------------------------------------------------------------
# Small helper widget for group items in the list
# ---------------------------------------------------------------------------

class _GroupSelected(Message):
    """Posted when a group is selected from the list."""

    def __init__(self, group_name: str) -> None:
        self.group_name = group_name
        super().__init__()


class _GroupListItem(ListItem):
    """A single group entry in the selection list.

    Renders as a single line of formatted text to avoid layout issues
    with nested containers inside ListItem.
    """

    DEFAULT_CSS = """
    _GroupListItem {
        height: 1;
        padding: 0 1;
    }
    _GroupListItem Static {
        height: 1;
        width: 1fr;
    }
    """

    def __init__(self, group: Any) -> None:
        self.group_data = group
        self.group_name: str = group.name
        super().__init__()

    def compose(self):
        name = self.group_data.name
        desc = self.group_data.description or ""
        if len(desc) > 35:
            desc = desc[:32] + "..."
        n_queries = len(self.group_data.queries)
        queries_label = f"{n_queries} consulta{'s' if n_queries != 1 else ''}"

        parts = [f"[bold]{name}[/bold]"]
        if desc:
            parts.append(f"[dim]{desc}[/dim]")
        parts.append(f"[#e3b341]{queries_label}[/#e3b341]")

        line = "  |  ".join(parts)
        yield Static(line, markup=True)


# ---------------------------------------------------------------------------
# GroupExecScreen
# ---------------------------------------------------------------------------


class GroupExecScreen(Vertical):
    """Screen widget for executing groups and comparing results.

    Phase 1 — group selection (folder tabs + list).
    Phase 2 — results (GroupResultWidget).
    """

    DEFAULT_CSS = """
    GroupExecScreen {
        height: 1fr;
    }
    GroupExecScreen #ge-selection-phase {
        height: 1fr;
    }
    GroupExecScreen #ge-results-phase {
        height: 1fr;
    }
    GroupExecScreen #ge-result-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    GroupExecScreen #ge-empty-message {
        height: 1fr;
        content-align: center middle;
        text-align: center;
    }
    GroupExecScreen #ge-folder-bar {
        height: 3;
        width: 1fr;
        padding: 0 1;
        background: $surface;
        scrollbar-size-horizontal: 1;
    }
    GroupExecScreen #ge-folder-bar Button {
        min-width: 6;
        margin: 0 1 0 0;
    }
    GroupExecScreen #ge-folder-hint {
        height: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: dim italic;
    }
    GroupExecScreen #ge-group-list {
        height: 1fr;
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
        self._current_group = None
        self._current_params: dict[str, str] = {}
        self._current_group_result: GroupResult | None = None
        self._raw_query_rows: dict[str, list[list]] | None = None  # original rows per query
        self._showing_mapped: bool = True
        self._all_groups: list = []
        self._folder_map: dict[str, str] = {}
        self._folder_buttons: list[Button] = []
        self._active_folder_idx: int = 0

    def compose(self) -> ComposeResult:
        # Selection phase
        with Vertical(id="ge-selection-phase"):
            yield Static(
                "[dim]Nenhum grupo configurado[/]",
                id="ge-empty-message",
                markup=True,
            )
        # Progress indicator (hidden by default)
        yield ProgressIndicator()
        # Results phase (hidden initially)
        with Vertical(id="ge-results-phase"):
            yield Static("", id="ge-result-info")
            yield GroupResultWidget(id="ge-group-result")

    def on_mount(self) -> None:
        self.query_one("#ge-results-phase").display = False
        self._load_selection()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        try:
            gl = self.query_one("#ge-group-list", ListView)
            gl.focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Phase 1: Group selection
    # ------------------------------------------------------------------

    def _load_selection(self) -> None:
        """Load groups and build the selection UI."""
        from dbqm.models.group import load_groups

        groups = load_groups()
        selection = self.query_one("#ge-selection-phase")
        empty_msg = self.query_one("#ge-empty-message", Static)

        if not groups:
            empty_msg.display = True
            return

        empty_msg.display = False
        self._all_groups = groups

        # Determine folders
        folders = sorted({g.folder for g in groups if g.folder})

        group_list = ListView(id="ge-group-list")

        if folders:
            folder_bar = HorizontalScroll(id="ge-folder-bar")
            selection.mount(folder_bar)
            btn_todas = Button("Todas", id="ge-folder-todas", variant="primary")
            folder_bar.mount(btn_todas)
            self._folder_buttons = [btn_todas]
            for folder in folders:
                safe_id = sanitize_id(folder)
                self._folder_map[safe_id] = folder
                btn = Button(folder, id=f"ge-folder-{safe_id}", variant="default")
                folder_bar.mount(btn)
                self._folder_buttons.append(btn)
            has_no_folder = any(not g.folder for g in groups)
            if has_no_folder:
                btn_sem = Button("Sem pasta", id="ge-folder-sem-pasta", variant="default")
                folder_bar.mount(btn_sem)
                self._folder_buttons.append(btn_sem)
            # Hint for keyboard navigation
            selection.mount(Static("[dim]← → alternar pastas[/dim]", id="ge-folder-hint", markup=True))
            self._active_folder_idx = 0

        selection.mount(group_list)
        self._populate_group_list(groups)

    def _populate_group_list(self, groups: list) -> None:
        """Populate the group ListView."""
        group_list = self.query_one("#ge-group-list", ListView)
        group_list.clear()
        sorted_groups = sorted(groups, key=lambda g: g.name.lower())
        if not sorted_groups:
            group_list.append(
                ListItem(Static("[dim]Nenhum grupo configurado[/]", markup=True))
            )
            return
        for g in sorted_groups:
            group_list.append(_GroupListItem(g))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle folder filter button presses."""
        btn_id = event.button.id or ""
        if not btn_id.startswith("ge-folder-"):
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
        """Activate a folder button and filter the group list."""
        for b in self._folder_buttons:
            b.variant = "default"
        btn.variant = "primary"

        btn_id = btn.id or ""
        safe_id = btn_id.removeprefix("ge-folder-")

        if safe_id == "todas":
            self._populate_group_list(self._all_groups)
        elif safe_id == "sem-pasta":
            self._populate_group_list([g for g in self._all_groups if not g.folder])
        else:
            folder_label = self._folder_map.get(safe_id, "")
            self._populate_group_list(
                [g for g in self._all_groups if g.folder == folder_label]
            )
        # Keep focus on the list
        try:
            self.query_one("#ge-group-list", ListView).focus()
        except Exception:
            pass

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle group selection from the list."""
        item = event.item
        if isinstance(item, _GroupListItem):
            self._on_group_chosen(item.group_name)

    # ------------------------------------------------------------------
    # Group selected -> parameterize & execute
    # ------------------------------------------------------------------

    def _on_group_chosen(self, group_name: str) -> None:
        """Handle group selection."""
        from dbqm.models.group import find_group

        group = find_group(group_name)
        if group is None:
            self.notify(f"Grupo '{group_name}' nao encontrado.", severity="error")
            return

        self._current_group = group

        # Build shared params list from the group
        if group.shared_params:
            self._push_param_modal(group)
        else:
            self._execute(group, {})

    def _push_param_modal(self, group, last_values: dict[str, str] | None = None) -> None:
        """Push the parameter input modal for shared params."""
        from dbqm.ui.modals.param_input import ParamModal

        params_dicts = []
        for name, value in group.shared_params.items():
            if isinstance(value, dict):
                params_dicts.append({
                    "name": name,
                    "description": value.get("description", ""),
                    "default": str(value.get("default", "")) if value.get("default") else "",
                })
            else:
                params_dicts.append({
                    "name": name,
                    "description": "",
                    "default": str(value) if value and not isinstance(value, str) else (value or ""),
                })

        modal = ParamModal(
            query_name=group.name,
            params=params_dicts,
            last_values=last_values or self._current_params,
            description=group.description,
        )
        self.app.push_screen(modal, callback=self._on_params_submitted)

    def _on_params_submitted(self, result: dict[str, str] | None) -> None:
        """Callback from ParamModal."""
        if result is None:
            return
        self._execute(self._current_group, result)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute(self, group, params: dict[str, str]) -> None:
        """Start group execution in a worker thread."""
        self._current_params = params
        self.query_one(ProgressIndicator).start(
            f"Executando grupo [bold]{escape_markup(group.name)}[/] ({len(group.queries)} consultas)..."
        )
        self._run_group(group, params)

    @work(thread=True)
    def _run_group(self, group, param_values: dict[str, str]) -> None:
        """Execute all queries in the group and build comparison."""
        import copy
        from dbqm.models.query import find_query
        from dbqm.models.connection import find_connection
        from dbqm.core.query_engine import execute_query
        from dbqm.core.group_engine import build_group_result

        try:
            query_results = {}
            raw_rows_map = {}
            has_any_maps = False
            start_time = time.time()

            for qname in group.queries:
                query = find_query(qname)
                if query is None:
                    self.app.call_from_thread(
                        self.notify,
                        f"Consulta '{qname}' nao encontrada no grupo.",
                        severity="warning",
                    )
                    continue

                conn = find_connection(query.connection)
                if conn is None:
                    self.app.call_from_thread(
                        self.notify,
                        f"Conexao '{query.connection}' nao encontrada para '{qname}'.",
                        severity="warning",
                    )
                    continue

                # Merge shared params with query-specific defaults
                q_params = dict(param_values)
                for p in query.params:
                    if p.name not in q_params:
                        q_params[p.name] = p.default or ""

                self.app.call_from_thread(
                    self._update_progress,
                    f"Executando [bold]{escape_markup(qname)}[/] em [bold]{escape_markup(conn.name)}[/]...",
                )

                try:
                    result = execute_query(query, conn, q_params)
                except Exception as e:
                    self.app.call_from_thread(
                        self.notify,
                        f"Erro em '{qname}': {e}",
                        severity="error",
                        timeout=8,
                    )
                    continue

                # Save raw rows before column maps
                if result.success and result.rows and query.column_maps:
                    raw_rows_map[qname] = copy.deepcopy(result.rows)
                    has_any_maps = True

                # Apply column maps
                if result.success and result.rows:
                    query.apply_column_maps(result.rows, result.columns)

                query_results[qname] = result

            elapsed = time.time() - start_time

            if not query_results:
                self.app.call_from_thread(self._on_error, "Nenhuma consulta executada com sucesso.")
                return

            # Check for failed queries
            failures = {k: v for k, v in query_results.items() if not v.success}
            if failures:
                for qn, res in failures.items():
                    self.app.call_from_thread(
                        self.notify,
                        f"Erro em '{qn}': {res.error}",
                        severity="error",
                        timeout=8,
                    )

            # Only compare successful results
            success_results = {k: v for k, v in query_results.items() if v.success}

            if len(success_results) < 2:
                self.app.call_from_thread(
                    self._on_error,
                    "Necessario pelo menos 2 consultas com sucesso para comparar.",
                )
                return

            group_result = build_group_result(
                group_name=group.name,
                query_results=success_results,
                join_key=group.join_key,
                compare_columns=group.compare_columns,
                column_mapping=group.column_mapping or None,
                normalize=group.normalize or None,
            )

            # Record history
            self._record_execution(group, param_values, group_result, elapsed)

            self.app.call_from_thread(
                self._show_result, group_result, param_values,
                raw_rows_map if has_any_maps else None,
            )
        except Exception as e:
            self.app.call_from_thread(self._on_error, f"Erro inesperado: {e}")

    def _update_progress(self, msg: str) -> None:
        """Update progress message (safe to call from main thread via call_from_thread)."""
        progress = self.query_one(ProgressIndicator)
        if progress:
            progress.update_message(msg)

    def _on_error(self, message: str) -> None:
        """Handle execution error on main thread."""
        self.query_one(ProgressIndicator).stop()
        self.notify(message, severity="error", timeout=8)

    def _show_result(self, group_result: GroupResult, param_values: dict[str, str], raw_rows_map: dict | None = None) -> None:
        """Display the group result on the main thread."""
        self.query_one(ProgressIndicator).stop()
        self._current_group_result = group_result
        self._raw_query_rows = raw_rows_map
        self._showing_mapped = True

        # Switch to results phase
        self.query_one("#ge-selection-phase").display = False
        results_phase = self.query_one("#ge-results-phase")
        results_phase.display = True

        # Update info bar
        overall = "CONSISTENTE" if group_result.all_match else "DIVERGENTE"
        overall_color = "green" if group_result.all_match else "yellow"
        group_name = str(group_result.group_name) if group_result.group_name else ""
        info = self.query_one("#ge-result-info", Static)
        info.update(
            f"[bold]{escape_markup(group_name)}[/] | "
            f"{len(group_result.query_results)} consultas | "
            f"[{overall_color} bold]{overall}[/]"
        )

        # Load result into GroupResultWidget
        grw = self.query_one("#ge-group-result", GroupResultWidget)
        grw.load_result(group_result)

        # Set up action bar
        self._set_result_actions()

    def _record_execution(self, group, params: dict, group_result: GroupResult, elapsed: float) -> None:
        """Record execution in history/audit."""
        try:
            from dbqm.core.history import record_group_execution
            summary_lines = [str(line) for line in group_result.summary_lines]
            record_group_execution(
                group_name=str(group.name),
                params=params,
                all_match=group_result.all_match,
                summary="\n".join(summary_lines),
                elapsed=elapsed,
            )
        except Exception:
            pass

        try:
            from dbqm.core.audit import log_execution
            log_execution(
                "group",
                str(group.name),
                "",
                params,
                0,
                True,
                "",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Action bar
    # ------------------------------------------------------------------

    def _set_result_actions(self) -> None:
        """Configure the action bar for results view."""
        try:
            action_bar = self.app.query_one(ActionBar)
        except Exception:
            return

        actions = [
            Action("Flat/Pivot", "F", "toggle_mode"),
            Action("Filtrar", "S", "filter_status"),
        ]
        if self._raw_query_rows is not None:
            label = "Original" if self._showing_mapped else "De-Para"
            actions.append(Action(label, "M", "toggle_mapping"))
        actions.extend([
            Action("Exportar", "E", "export"),
            Action("HTML", "H", "export_html"),
            Action("Individual", "I", "view_individual"),
            Action("Reexecutar", "R", "reexecute"),
        ])
        action_bar.set_actions(actions)

    def on_action_selected(self, message: ActionSelected) -> None:
        """Handle action bar selections."""
        action = message.action_id

        if action == "toggle_mode":
            self._handle_toggle_mode()
        elif action == "filter_status":
            self._handle_filter_status()
        elif action == "toggle_mapping":
            self._handle_toggle_mapping()
        elif action == "export":
            self._handle_export()
        elif action == "export_html":
            self._handle_export_html()
        elif action == "view_individual":
            self._handle_view_individual()
        elif action == "reexecute":
            self._handle_reexecute()

    def _handle_toggle_mode(self) -> None:
        grw = self.query_one("#ge-group-result", GroupResultWidget)
        grw.toggle_mode()

    def _handle_toggle_mapping(self) -> None:
        """Toggle between mapped (de-para) and original values in group results."""
        import copy
        if self._current_group_result is None or self._raw_query_rows is None:
            return

        from dbqm.models.query import find_query
        from dbqm.core.group_engine import build_group_result

        gr = self._current_group_result
        for qname, result in gr.query_results.items():
            if qname in self._raw_query_rows:
                if self._showing_mapped:
                    # Restore original rows
                    result.rows = copy.deepcopy(self._raw_query_rows[qname])
                else:
                    # Re-apply column maps
                    result.rows = copy.deepcopy(self._raw_query_rows[qname])
                    query = find_query(qname)
                    if query:
                        query.apply_column_maps(result.rows, result.columns)

        # Rebuild comparison with current row data
        new_gr = build_group_result(
            group_name=gr.group_name,
            query_results=gr.query_results,
            join_key=self._current_group.join_key,
            compare_columns=self._current_group.compare_columns,
            column_mapping=self._current_group.column_mapping or None,
            normalize=self._current_group.normalize or None,
        )
        self._current_group_result = new_gr

        self._showing_mapped = not self._showing_mapped

        grw = self.query_one("#ge-group-result", GroupResultWidget)
        grw.load_result(new_gr)
        self._set_result_actions()

        label = "mapeados (de-para)" if self._showing_mapped else "originais"
        self.notify(f"Exibindo valores {label}", timeout=2)

    def _handle_filter_status(self) -> None:
        """Push a status filter dialog."""
        from dbqm.ui.modals.confirm import ConfirmModal

        # Simple approach: cycle through filter presets
        grw = self.query_one("#ge-group-result", GroupResultWidget)

        if grw._status_filter is None:
            grw.filter_status({"DIFF", "ABSENT"})
            self.notify("Filtro: DIFF + ABSENT", timeout=3)
        elif grw._status_filter == {"DIFF", "ABSENT"}:
            grw.filter_status({"DIFF"})
            self.notify("Filtro: apenas DIFF", timeout=3)
        elif grw._status_filter == {"DIFF"}:
            grw.filter_status({"ABSENT"})
            self.notify("Filtro: apenas ABSENT", timeout=3)
        else:
            grw.filter_status(set())
            self.notify("Filtro removido — mostrando todos", timeout=3)

    def _handle_export(self) -> None:
        from dbqm.ui.modals.export_picker import ExportPickerModal

        modal = ExportPickerModal(include_png=False)
        self.app.push_screen(modal, callback=self._on_export_format_selected)

    def _on_export_format_selected(self, fmt: str | None) -> None:
        """Callback from ExportPickerModal."""
        if fmt is None or self._current_group_result is None:
            return

        from dbqm.core.exporter import (
            export_group_csv, export_group_json, export_group_txt,
            export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
        )

        params = self._current_params
        gr = self._current_group_result
        grw = self.query_one("#ge-group-result", GroupResultWidget)
        is_flat = grw.mode == "flat"

        try:
            if fmt == "csv":
                path = export_group_flat_csv(gr, params) if is_flat else export_group_csv(gr, params)
            elif fmt == "json":
                path = export_group_flat_json(gr, params) if is_flat else export_group_json(gr, params)
            elif fmt == "txt":
                path = export_group_flat_txt(gr, params) if is_flat else export_group_txt(gr, params)
            else:
                self.notify(f"Formato '{fmt}' nao suportado.", severity="warning")
                return

            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    def _handle_export_html(self) -> None:
        if self._current_group_result is None:
            return

        from dbqm.core.html_report import export_group_html

        try:
            path = export_group_html(self._current_group_result, self._current_params)
            self.notify(f"Relatorio HTML exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar HTML: {e}", severity="error")

    def _handle_view_individual(self) -> None:
        """Show individual query result — cycle through queries or push a selector."""
        if self._current_group_result is None:
            return

        query_names = list(self._current_group_result.query_results.keys())
        if not query_names:
            return

        # Push a simple selector modal to pick which query to view
        from dbqm.ui.screens.group_exec import _QueryPickerModal
        modal = _QueryPickerModal(query_names)
        self.app.push_screen(modal, callback=self._on_individual_query_selected)

    def _on_individual_query_selected(self, query_name: str | None) -> None:
        """Show individual ResultTable for the selected query."""
        if query_name is None or self._current_group_result is None:
            return

        result = self._current_group_result.query_results.get(query_name)
        if result is None:
            return

        from dbqm.ui.screens.group_exec import _IndividualResultModal
        modal = _IndividualResultModal(query_name, result)
        self.app.push_screen(modal)

    def _handle_reexecute(self) -> None:
        if self._current_group is None:
            return
        # Go back to selection or directly re-run
        if self._current_group.shared_params:
            self._push_param_modal(self._current_group, last_values=self._current_params)
        else:
            self._execute(self._current_group, self._current_params)

    # ------------------------------------------------------------------
    # Back navigation support
    # ------------------------------------------------------------------

    def go_back_to_selection(self) -> None:
        """Return to the group selection phase."""
        self.query_one("#ge-selection-phase").display = True
        self.query_one("#ge-results-phase").display = False
        self._current_group_result = None
        self._raw_query_rows = None
        self._showing_mapped = True

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions([])
        except Exception:
            pass

        # Restore focus to group list
        try:
            from textual.widgets import ListView
            self.query_one("#ge-group-list", ListView).focus()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helper modals for group execution
# ---------------------------------------------------------------------------

from textual.binding import Binding
from textual.screen import ModalScreen

from dbqm.core.query_engine import QueryResult


class _QueryPickerModal(ModalScreen[str | None]):
    """Simple modal to select which query to view individually."""

    DEFAULT_CSS = """
    _QueryPickerModal {
        align: center middle;
    }
    _QueryPickerModal #qp-dialog {
        width: 50;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _QueryPickerModal #qp-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _QueryPickerModal Button {
        width: 100%;
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, query_names: list[str]) -> None:
        super().__init__()
        self._query_names = query_names
        self._qname_map: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="qp-dialog"):
            yield Static("Selecionar consulta", id="qp-title")
            for qn in self._query_names:
                safe_id = sanitize_id(qn)
                self._qname_map[safe_id] = qn
                yield Button(qn, variant="primary", id=f"qp-{safe_id}")
            yield Button("Cancelar", variant="default", id="qp--cancel--")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "qp--cancel--":
            self.dismiss(None)
        elif btn_id.startswith("qp-"):
            safe_id = btn_id.removeprefix("qp-")
            qn = self._qname_map.get(safe_id)
            if qn:
                self.dismiss(qn)

    def action_cancel(self) -> None:
        self.dismiss(None)


class _IndividualResultModal(ModalScreen[None]):
    """Modal that shows a single query result in a ResultTable."""

    DEFAULT_CSS = """
    _IndividualResultModal {
        align: center middle;
    }
    _IndividualResultModal #ir-dialog {
        width: 90%;
        height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _IndividualResultModal #ir-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _IndividualResultModal #ir-info {
        height: auto;
        color: $text-muted;
        padding: 0 0 1 0;
    }
    _IndividualResultModal #ir-close {
        width: 100%;
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Fechar", show=False),
    ]

    def __init__(self, query_name: str, result: QueryResult) -> None:
        super().__init__()
        self._query_name = query_name
        self._result = result

    def compose(self) -> ComposeResult:
        with Vertical(id="ir-dialog"):
            yield Static(self._query_name, id="ir-title")
            yield Static(
                f"{self._result.row_count} registros | "
                f"{self._result.elapsed:.2f}s | "
                f"{self._result.connection_name}",
                id="ir-info",
            )
            yield ResultTable(id="ir-result-table")
            yield Button("Fechar", variant="default", id="ir-close")

    def on_mount(self) -> None:
        rt = self.query_one("#ir-result-table", ResultTable)
        rt.load_result(self._result)
        rt.focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ir-close":
            self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
