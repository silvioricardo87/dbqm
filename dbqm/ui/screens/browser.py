"""Object browser screen — browse tables, views, packages, and routines."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, Select, Static
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.result_table import ResultTable
from dbqm.ui.widgets.sql_viewer import SqlViewer

DEFAULT_LIMIT = 100


class BrowserScreen(Vertical):
    """Screen widget for browsing database objects.

    Phase 1 — connection + object type selection.
    Phase 2 — object list with filter.
    Phase 3 — object detail (structure, definition, routines).
    """

    DEFAULT_CSS = """
    BrowserScreen {
        height: 1fr;
    }
    BrowserScreen #br-select-phase {
        height: auto;
        padding: 1;
    }
    BrowserScreen #br-conn-bar {
        height: auto;
        padding: 0 0 1 0;
    }
    BrowserScreen #br-conn-bar Select {
        width: 1fr;
    }
    BrowserScreen #br-type-bar {
        height: auto;
        padding: 0 0 1 0;
        align: center middle;
    }
    BrowserScreen #br-type-bar Button {
        margin: 0 1;
    }
    BrowserScreen #br-list-phase {
        height: 1fr;
        padding: 0 1;
    }
    BrowserScreen #br-filter-bar {
        height: auto;
        padding: 0 0 1 0;
    }
    BrowserScreen #br-filter-bar Input {
        width: 1fr;
    }
    BrowserScreen #br-filter-bar Button {
        margin: 0 0 0 1;
    }
    BrowserScreen #br-object-table {
        height: 1fr;
        max-height: 20;
    }
    BrowserScreen #br-detail-phase {
        height: 1fr;
        padding: 0 1;
    }
    BrowserScreen #br-detail-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    BrowserScreen #br-structure-table {
        height: 1fr;
        max-height: 15;
    }
    BrowserScreen #br-index-info {
        height: auto;
        padding: 1 1 0 1;
    }
    BrowserScreen #br-sql-viewer {
        height: 1fr;
        max-height: 100%;
    }
    BrowserScreen #br-routine-table {
        height: 1fr;
        max-height: 15;
    }
    BrowserScreen #br-data-phase {
        height: 1fr;
        padding: 0 1;
    }
    BrowserScreen #br-data-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
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
        self._query_limit = DEFAULT_LIMIT
        self._query_offset = 0

    def compose(self) -> ComposeResult:
        # Phase 1: Connection + type selection
        with Vertical(id="br-select-phase"):
            with Horizontal(id="br-conn-bar"):
                yield Select([], prompt="Selecione a conexao", id="br-conn-select")
            with Horizontal(id="br-type-bar"):
                yield Button("Tabelas", id="br-type-table")
                yield Button("Views", id="br-type-view")
                yield Button("Packages", id="br-type-package")
                yield Button("Rotinas", id="br-type-routine")

        # Progress indicator
        yield ProgressIndicator()

        # Phase 2: Object list
        with Vertical(id="br-list-phase"):
            with Horizontal(id="br-filter-bar"):
                yield Input(placeholder="Filtrar objetos...", id="br-filter-input")
                yield Button("Filtrar", id="br-filter-btn")
            yield DataTable(id="br-object-table")

        # Phase 3: Object detail
        with Vertical(id="br-detail-phase"):
            yield Static("", id="br-detail-info")
            yield DataTable(id="br-structure-table")
            yield Static("", id="br-index-info")
            yield SqlViewer("", id="br-sql-viewer")
            yield DataTable(id="br-routine-table")

        # Phase 3b: Data query results
        with Vertical(id="br-data-phase"):
            yield Static("", id="br-data-info")
            yield ResultTable(id="br-data-result")

    def on_mount(self) -> None:
        self.query_one("#br-list-phase").display = False
        self.query_one("#br-detail-phase").display = False
        self.query_one("#br-data-phase").display = False
        self._load_connections()
        self._setup_type_buttons()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#br-conn-select", Select).focus()
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
        select_widget = self.query_one("#br-conn-select", Select)
        select_widget.set_options(options)

        if not connections:
            self.notify("Nenhuma conexao configurada.", severity="warning")

    def _setup_type_buttons(self) -> None:
        """Show/hide type buttons based on selected connection's db_type."""
        # Initially hide package/routine; they'll be shown when connection is selected
        self.query_one("#br-type-package", Button).display = False
        self.query_one("#br-type-routine", Button).display = False

    def _get_selected_conn(self):
        """Get the currently selected connection object."""
        from dbqm.models.connection import find_connection

        select_widget = self.query_one("#br-conn-select", Select)
        conn_name = select_widget.value
        if conn_name is Select.BLANK:
            self.notify("Selecione uma conexao.", severity="warning")
            return None
        conn = find_connection(conn_name)
        if not conn:
            self.notify("Conexao nao encontrada.", severity="error")
            return None
        return conn

    # ------------------------------------------------------------------
    # Connection change handler
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        """When connection changes, update type button visibility."""
        if event.select.id != "br-conn-select":
            return

        conn = self._get_selected_conn()
        if not conn:
            return

        self._current_conn = conn
        pkg_btn = self.query_one("#br-type-package", Button)
        routine_btn = self.query_one("#br-type-routine", Button)

        if conn.db_type == "oracle":
            pkg_btn.display = True
            routine_btn.display = False
        elif conn.db_type in ("postgresql", "mysql"):
            pkg_btn.display = False
            routine_btn.display = True
        else:
            pkg_btn.display = False
            routine_btn.display = False

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id.startswith("br-type-"):
            self._handle_type_selection(btn_id)
        elif btn_id == "br-filter-btn":
            self._apply_filter()

    def _handle_type_selection(self, btn_id: str) -> None:
        """Handle object type button click."""
        conn = self._get_selected_conn()
        if not conn:
            return

        self._current_conn = conn
        type_map = {
            "br-type-table": "TABLE",
            "br-type-view": "VIEW",
            "br-type-package": "PACKAGE",
            "br-type-routine": "ROUTINE",
        }
        self._obj_type = type_map.get(btn_id, "")
        if not self._obj_type:
            return

        self.query_one(ProgressIndicator).start(
            f"Listando objetos em [bold]{conn.name}[/]..."
        )
        self._load_objects(conn, self._obj_type)

    @work(thread=True)
    def _load_objects(self, conn, obj_type: str) -> None:
        """Load object list in background thread."""
        from dbqm.core.db_manager import get_connection
        from dbqm.core.object_browser import list_objects

        try:
            if self._db is None:
                self._db = get_connection(conn)

            objects = list_objects(self._db, conn.db_type, obj_type)
            self.call_from_thread(self._on_objects_loaded, objects)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_objects_loaded(self, objects: list[str]) -> None:
        """Handle objects loaded."""
        self.query_one(ProgressIndicator).stop()
        self._objects = objects

        if not objects:
            self.notify("Nenhum objeto encontrado.", severity="warning")
            return

        # Switch to list phase
        self.query_one("#br-select-phase").display = False
        self.query_one("#br-list-phase").display = True
        self.query_one("#br-detail-phase").display = False
        self.query_one("#br-data-phase").display = False

        self._populate_object_table(objects)

        # Set up action bar
        self._set_list_actions()

    def _on_load_error(self, error: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro: {error}", severity="error", timeout=8)

    def _populate_object_table(self, objects: list[str]) -> None:
        """Populate the object list DataTable."""
        type_labels = {
            "TABLE": "Tabela",
            "VIEW": "View",
            "PACKAGE": "Package",
            "ROUTINE": "Rotina",
        }
        label = type_labels.get(self._obj_type, "Objeto")

        table = self.query_one("#br-object-table", DataTable)
        table.clear(columns=True)
        table.add_column("#", key="num")
        table.add_column(label, key="name")
        table.cursor_type = "row"

        display_objects = objects[:200]
        for i, obj in enumerate(display_objects, 1):
            table.add_row(str(i), obj, key=obj)

        if len(objects) > 200:
            self.notify(
                f"{len(objects)} objetos encontrados. Exibindo os primeiros 200. Use o filtro.",
                severity="information",
                timeout=5,
            )

    def _apply_filter(self) -> None:
        """Filter the object list."""
        filter_text = self.query_one("#br-filter-input", Input).value.strip()
        if filter_text:
            filtered = [o for o in self._objects if filter_text.upper() in o.upper()]
        else:
            filtered = self._objects

        if not filtered:
            self.notify("Nenhum objeto encontrado com esse filtro.", severity="warning")
            return

        self._populate_object_table(filtered)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Filter on Enter in filter input."""
        if event.input.id == "br-filter-input":
            self._apply_filter()

    # ------------------------------------------------------------------
    # Object selection (from DataTable)
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle object selection from the list."""
        table_id = event.data_table.id or ""

        if table_id == "br-object-table":
            obj_name = str(event.row_key.value)
            self._selected_object = obj_name
            self._load_object_detail(obj_name)

    def _load_object_detail(self, obj_name: str) -> None:
        """Load detail for the selected object."""
        self.query_one(ProgressIndicator).start(
            f"Carregando [bold]{obj_name}[/]..."
        )

        if self._obj_type == "TABLE":
            self._load_table_structure(obj_name)
        elif self._obj_type == "VIEW":
            self._load_view_definition(obj_name)
        elif self._obj_type == "PACKAGE":
            self._load_package_routines(obj_name)
        elif self._obj_type == "ROUTINE":
            self._load_routine_detail(obj_name)

    # ------------------------------------------------------------------
    # Table structure
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_table_structure(self, table_name: str) -> None:
        from dbqm.core.object_browser import get_table_structure

        try:
            structure = get_table_structure(
                self._db, self._current_conn.db_type, table_name
            )
            self.call_from_thread(self._on_table_structure_loaded, structure)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_table_structure_loaded(self, structure) -> None:
        """Display table structure."""
        self.query_one(ProgressIndicator).stop()

        # Switch to detail phase
        self.query_one("#br-list-phase").display = False
        detail = self.query_one("#br-detail-phase")
        detail.display = True
        self.query_one("#br-data-phase").display = False

        # Info bar
        info = self.query_one("#br-detail-info", Static)
        info.update(
            f"[bold]Tabela:[/] {str(structure.table)} | "
            f"{len(structure.columns)} colunas | "
            f"{len(structure.indexes)} indices | "
            f"{structure.elapsed:.2f}s"
        )

        # Structure table
        struct_table = self.query_one("#br-structure-table", DataTable)
        struct_table.display = True
        struct_table.clear(columns=True)
        struct_table.cursor_type = "row"
        struct_table.add_column("Coluna", key="col")
        struct_table.add_column("Tipo", key="type")
        struct_table.add_column("Tamanho", key="size")
        struct_table.add_column("Nullable", key="null")
        struct_table.add_column("Chave", key="key")

        for col in structure.columns:
            if col.data_precision is not None:
                size = f"{col.data_precision}"
                if col.data_scale is not None and col.data_scale > 0:
                    size += f",{col.data_scale}"
            elif col.data_length is not None:
                size = str(col.data_length)
            else:
                size = ""

            key_parts = []
            if col.is_pk:
                key_parts.append("PK")
            if col.fk_ref:
                key_parts.append(f"FK -> {col.fk_ref}")
            key = " ".join(key_parts)

            struct_table.add_row(
                str(col.name), str(col.data_type), str(size),
                "Y" if col.nullable else "N", str(key)
            )

        # Index info
        index_info = self.query_one("#br-index-info", Static)
        if structure.indexes:
            idx_lines = ["[bold]Indices:[/]"]
            for idx in structure.indexes:
                unique = " (UNIQUE)" if idx.is_unique else ""
                cols = ", ".join(idx.columns)
                idx_lines.append(f"  {idx.name}{unique}: {cols}")
            index_info.update("\n".join(idx_lines))
            index_info.display = True
        else:
            index_info.update("")
            index_info.display = False

        # Hide other detail widgets
        self.query_one("#br-sql-viewer", SqlViewer).display = False
        self.query_one("#br-routine-table", DataTable).display = False

        # Store structure for export
        self._current_structure = structure

        # Action bar
        self._set_table_detail_actions()

    def _set_table_detail_actions(self) -> None:
        actions = [
            Action("Consultar dados", "Q", "br_query_data"),
            Action("Exportar estrutura", "E", "br_export_structure"),
            Action("Voltar", "Esc", "br_back_to_list"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # View definition
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_view_definition(self, view_name: str) -> None:
        from dbqm.core.object_browser import get_view_definition

        try:
            view_info = get_view_definition(
                self._db, self._current_conn.db_type, view_name
            )
            self.call_from_thread(self._on_view_loaded, view_info)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_view_loaded(self, view_info) -> None:
        """Display view definition."""
        self.query_one(ProgressIndicator).stop()

        self.query_one("#br-list-phase").display = False
        detail = self.query_one("#br-detail-phase")
        detail.display = True
        self.query_one("#br-data-phase").display = False

        info = self.query_one("#br-detail-info", Static)
        info.update(f"[bold]View:[/] {str(view_info.name)} | Owner: {str(view_info.owner)}")

        # Hide table-specific widgets
        self.query_one("#br-structure-table", DataTable).display = False
        self.query_one("#br-index-info", Static).display = False
        self.query_one("#br-routine-table", DataTable).display = False

        # Show SQL definition
        sql_viewer = self.query_one("#br-sql-viewer", SqlViewer)
        sql_viewer.display = True
        sql_viewer.set_sql(view_info.sql_definition or "-- Definicao nao disponivel")

        self._current_view_info = view_info

        # Action bar
        actions = [
            Action("Consultar dados", "Q", "br_query_data"),
            Action("Exportar definicao", "E", "br_export_view"),
            Action("Voltar", "Esc", "br_back_to_list"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Package routines
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_package_routines(self, pkg_name: str) -> None:
        from dbqm.core.object_browser import list_package_routines

        try:
            pkg_info = list_package_routines(
                self._db, self._current_conn.db_type, pkg_name
            )
            self.call_from_thread(self._on_package_loaded, pkg_info)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_package_loaded(self, pkg_info) -> None:
        """Display package routines."""
        self.query_one(ProgressIndicator).stop()

        self.query_one("#br-list-phase").display = False
        detail = self.query_one("#br-detail-phase")
        detail.display = True
        self.query_one("#br-data-phase").display = False

        info = self.query_one("#br-detail-info", Static)
        info.update(
            f"[bold]Package:[/] {pkg_info.name} | "
            f"Owner: {pkg_info.owner} | "
            f"{len(pkg_info.routines)} rotinas"
        )

        # Hide table/view-specific widgets
        self.query_one("#br-structure-table", DataTable).display = False
        self.query_one("#br-index-info", Static).display = False
        self.query_one("#br-sql-viewer", SqlViewer).display = False

        # Show routine table
        routine_table = self.query_one("#br-routine-table", DataTable)
        routine_table.display = True
        routine_table.clear(columns=True)
        routine_table.cursor_type = "row"
        routine_table.add_column("Tipo", key="type")
        routine_table.add_column("Nome", key="name")
        routine_table.add_column("Assinatura", key="sig")

        for r in pkg_info.routines:
            routine_table.add_row(r.routine_type, r.name, r.signature)

        self._current_pkg_info = pkg_info

        # Action bar
        actions = [
            Action("Ver spec", "S", "br_view_spec"),
            Action("Ver body", "B", "br_view_body"),
            Action("Exportar package", "E", "br_export_package"),
            Action("Voltar", "Esc", "br_back_to_list"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Routine detail (PostgreSQL/MySQL)
    # ------------------------------------------------------------------

    @work(thread=True)
    def _load_routine_detail(self, routine_name: str) -> None:
        try:
            cursor = self._db.cursor()
            try:
                if self._current_conn.db_type == "postgresql":
                    cursor.execute("""
                        SELECT routine_type, data_type, routine_definition
                        FROM information_schema.routines
                        WHERE routine_name = %(name)s AND routine_schema = 'public'
                    """, {"name": routine_name})
                else:
                    cursor.execute("""
                        SELECT routine_type, data_type, routine_definition
                        FROM information_schema.routines
                        WHERE routine_name = %(name)s AND routine_schema = DATABASE()
                    """, {"name": routine_name})
                row = cursor.fetchone()
            finally:
                cursor.close()

            if row:
                rtype, rdata, rdef = row
                self.call_from_thread(
                    self._on_routine_loaded, routine_name, rtype, rdata, rdef
                )
            else:
                self.call_from_thread(
                    self._on_load_error, "Rotina nao encontrada."
                )
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_routine_loaded(
        self, routine_name: str, rtype: str, rdata: str, rdef: str | None
    ) -> None:
        """Display routine detail."""
        self.query_one(ProgressIndicator).stop()

        self.query_one("#br-list-phase").display = False
        detail = self.query_one("#br-detail-phase")
        detail.display = True
        self.query_one("#br-data-phase").display = False

        info = self.query_one("#br-detail-info", Static)
        ret_info = f" | Retorno: {rdata}" if rdata else ""
        info.update(f"[bold]{rtype}:[/] {routine_name}{ret_info}")

        # Hide table/pkg-specific widgets
        self.query_one("#br-structure-table", DataTable).display = False
        self.query_one("#br-index-info", Static).display = False
        self.query_one("#br-routine-table", DataTable).display = False

        # Show SQL
        sql_viewer = self.query_one("#br-sql-viewer", SqlViewer)
        sql_viewer.display = True
        if rdef:
            sql_viewer.set_sql(rdef)
        else:
            sql_viewer.set_sql("-- Definicao nao disponivel (rotina compilada ou sem permissao)")

        # Action bar
        actions = [
            Action("Voltar", "Esc", "br_back_to_list"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Data query (tables and views)
    # ------------------------------------------------------------------

    def _handle_query_data(self) -> None:
        """Query data from the selected table/view."""
        if not self._selected_object or not self._current_conn:
            return

        self._query_offset = 0
        self._run_data_query()

    def _run_data_query(self) -> None:
        self.query_one(ProgressIndicator).start(
            f"Consultando [bold]{self._selected_object}[/]..."
        )
        self._execute_data_query(
            self._selected_object,
            self._current_conn,
            self._query_limit,
            self._query_offset,
        )

    @work(thread=True)
    def _execute_data_query(self, obj_name: str, conn, limit: int, offset: int) -> None:
        from dbqm.core.table_browser import browse_table, _validate_identifier

        try:
            result = browse_table(
                self._db, conn.db_type, obj_name, conn.name, limit, offset
            )
            self.call_from_thread(self._on_data_result, result)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_data_result(self, result) -> None:
        """Display data query results."""
        from dbqm.core.query_engine import QueryResult

        self.query_one(ProgressIndicator).stop()

        # Switch to data phase
        self.query_one("#br-detail-phase").display = False
        data_phase = self.query_one("#br-data-phase")
        data_phase.display = True

        # Info bar
        info = self.query_one("#br-data-info", Static)
        page_info = ""
        if result.total_count > 0:
            page_start = result.offset + 1
            page_end = min(result.offset + result.limit, result.total_count)
            page_info = f" | Exibindo {page_start}-{page_end} de {result.total_count}"
        info.update(
            f"[bold]{self._selected_object}[/] | {result.connection_name} | "
            f"{result.row_count} registros | {result.elapsed:.2f}s{page_info}"
        )

        # Result table
        qr = QueryResult(
            query_name=f"Dados: {self._selected_object}",
            connection_name=result.connection_name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        )
        result_table = self.query_one("#br-data-result", ResultTable)
        result_table.load_result(qr)

        self._current_browse_result = result
        self._current_data_qr = qr

        # Action bar with pagination
        self._set_data_actions(result)

    def _set_data_actions(self, result) -> None:
        actions = [
            Action("Exportar", "E", "br_export_data"),
        ]
        if result.offset + result.limit < result.total_count:
            actions.append(Action("Proxima", "N", "br_next_page"))
        if result.offset > 0:
            actions.append(Action("Anterior", "P", "br_prev_page"))
        actions.append(Action("Voltar", "Esc", "br_back_to_detail"))

        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Package source viewing
    # ------------------------------------------------------------------

    def _handle_view_spec(self) -> None:
        if not hasattr(self, '_current_pkg_info'):
            return
        self.query_one(ProgressIndicator).start("Carregando spec...")
        self._load_package_source(self._current_pkg_info.name, "PACKAGE")

    def _handle_view_body(self) -> None:
        if not hasattr(self, '_current_pkg_info'):
            return
        self.query_one(ProgressIndicator).start("Carregando body...")
        self._load_package_source(self._current_pkg_info.name, "PACKAGE BODY")

    @work(thread=True)
    def _load_package_source(self, pkg_name: str, source_type: str) -> None:
        from dbqm.core.object_browser import get_package_source

        try:
            source = get_package_source(
                self._db, self._current_conn.db_type, pkg_name, source_type
            )
            self.call_from_thread(self._on_source_loaded, source, source_type, pkg_name)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_source_loaded(self, source: str, source_type: str, pkg_name: str) -> None:
        self.query_one(ProgressIndicator).stop()

        if not source:
            label = "Spec" if source_type == "PACKAGE" else "Body"
            self.notify(f"{label} nao encontrado.", severity="warning")
            return

        # Show in detail phase, replacing routine table
        self.query_one("#br-routine-table", DataTable).display = False
        sql_viewer = self.query_one("#br-sql-viewer", SqlViewer)
        sql_viewer.display = True

        label = "SPEC" if source_type == "PACKAGE" else "BODY"
        sql_viewer.set_sql(f"-- {label}: {pkg_name}\n\n{source}")

    # ------------------------------------------------------------------
    # Export handlers
    # ------------------------------------------------------------------

    def _handle_export_structure(self) -> None:
        """Export table structure."""
        if not hasattr(self, '_current_structure'):
            return

        from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt
        from dbqm.core.query_engine import QueryResult
        from dbqm.ui.modals.export_picker import ExportPickerModal

        modal = ExportPickerModal(include_png=False)
        self.app.push_screen(modal, callback=self._on_structure_export_format)

    def _on_structure_export_format(self, fmt: str | None) -> None:
        if fmt is None:
            return

        from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt
        from dbqm.core.query_engine import QueryResult

        structure = self._current_structure
        columns = ["Coluna", "Tipo", "Tamanho", "Nullable", "Chave"]
        rows = []
        for col in structure.columns:
            if col.data_precision is not None:
                size = f"{col.data_precision}"
                if col.data_scale is not None and col.data_scale > 0:
                    size += f",{col.data_scale}"
            elif col.data_length is not None:
                size = str(col.data_length)
            else:
                size = ""

            key_parts = []
            if col.is_pk:
                key_parts.append("PK")
            if col.fk_ref:
                key_parts.append(f"FK -> {col.fk_ref}")
            key = " ".join(key_parts)
            rows.append([col.name, col.data_type, size, "Y" if col.nullable else "N", key])

        qr = QueryResult(
            query_name=f"Estrutura: {structure.table}",
            connection_name=self._current_conn.name if self._current_conn else "",
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed=structure.elapsed,
        )

        try:
            if fmt == "csv":
                path = export_query_csv(qr, structure.table)
            elif fmt == "json":
                path = export_query_json(qr, structure.table)
            else:
                path = export_query_txt(qr, structure.table)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    def _handle_export_view(self) -> None:
        """Export view definition."""
        if not hasattr(self, '_current_view_info'):
            return

        from dbqm.core.exporter import export_sql_file

        try:
            view_info = self._current_view_info
            content = f"-- VIEW: {view_info.name}\n{view_info.sql_definition}"
            path = export_sql_file(content, view_info.name)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    def _handle_export_package(self) -> None:
        """Export package source."""
        if not hasattr(self, '_current_pkg_info'):
            return

        self.query_one(ProgressIndicator).start("Exportando package...")
        self._run_package_export(self._current_pkg_info.name)

    @work(thread=True)
    def _run_package_export(self, pkg_name: str) -> None:
        from dbqm.core.object_browser import get_package_source
        from dbqm.core.exporter import export_sql_file

        try:
            spec = get_package_source(self._db, self._current_conn.db_type, pkg_name, "PACKAGE")
            body = get_package_source(self._db, self._current_conn.db_type, pkg_name, "PACKAGE BODY")

            parts: list[str] = []
            if spec:
                parts.append(f"-- PACKAGE SPEC: {pkg_name}")
                parts.append(f"CREATE OR REPLACE {spec}")
                parts.append("/")
                parts.append("")
            if body:
                parts.append(f"-- PACKAGE BODY: {pkg_name}")
                parts.append(f"CREATE OR REPLACE {body}")
                parts.append("/")

            if not parts:
                self.call_from_thread(
                    self._on_load_error,
                    "Nenhum source encontrado para este package.",
                )
                return

            content = "\n".join(parts)
            path = export_sql_file(content, pkg_name)
            self.call_from_thread(self._on_package_exported, path)
        except Exception as e:
            self.call_from_thread(self._on_load_error, str(e))

    def _on_package_exported(self, path: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Exportado: {path}", timeout=5)

    def _handle_export_data(self) -> None:
        """Export query data."""
        if not hasattr(self, '_current_data_qr'):
            return

        from dbqm.ui.modals.export_picker import ExportPickerModal

        modal = ExportPickerModal(include_png=False)
        self.app.push_screen(modal, callback=self._on_data_export_format)

    def _on_data_export_format(self, fmt: str | None) -> None:
        if fmt is None or not hasattr(self, '_current_data_qr'):
            return

        from dbqm.core.exporter import export_query_csv, export_query_json, export_query_txt

        qr = self._current_data_qr
        table = self._selected_object

        try:
            if fmt == "csv":
                path = export_query_csv(qr, table)
            elif fmt == "json":
                path = export_query_json(qr, table)
            else:
                path = export_query_txt(qr, table)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "br_query_data":
            self._handle_query_data()
        elif action == "br_export_structure":
            self._handle_export_structure()
        elif action == "br_export_view":
            self._handle_export_view()
        elif action == "br_export_package":
            self._handle_export_package()
        elif action == "br_export_data":
            self._handle_export_data()
        elif action == "br_view_spec":
            self._handle_view_spec()
        elif action == "br_view_body":
            self._handle_view_body()
        elif action == "br_next_page":
            self._query_offset += self._query_limit
            self._run_data_query()
        elif action == "br_prev_page":
            self._query_offset = max(0, self._query_offset - self._query_limit)
            self._run_data_query()
        elif action == "br_back_to_list":
            self.go_back_to_list()
        elif action == "br_back_to_detail":
            self.go_back_to_detail()
        elif action == "br_back_to_select":
            self.go_back_to_select()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _set_list_actions(self) -> None:
        actions = [
            Action("Voltar", "Esc", "br_back_to_select"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    def go_back_to_select(self) -> None:
        """Return to connection/type selection."""
        self.query_one("#br-select-phase").display = True
        self.query_one("#br-list-phase").display = False
        self.query_one("#br-detail-phase").display = False
        self.query_one("#br-data-phase").display = False
        self._close_db()
        try:
            self.app.query_one(ActionBar).set_actions([])
        except Exception:
            pass

    def go_back_to_list(self) -> None:
        """Return to the object list."""
        self.query_one("#br-select-phase").display = False
        self.query_one("#br-list-phase").display = True
        self.query_one("#br-detail-phase").display = False
        self.query_one("#br-data-phase").display = False
        self._set_list_actions()

    def go_back_to_detail(self) -> None:
        """Return from data view to detail view."""
        self.query_one("#br-data-phase").display = False
        self.query_one("#br-detail-phase").display = True

        # Restore appropriate actions
        if self._obj_type == "TABLE":
            self._set_table_detail_actions()
        elif self._obj_type == "VIEW":
            actions = [
                Action("Consultar dados", "Q", "br_query_data"),
                Action("Exportar definicao", "E", "br_export_view"),
                Action("Voltar", "Esc", "br_back_to_list"),
            ]
            try:
                self.app.query_one(ActionBar).set_actions(actions)
            except Exception:
                pass

    def on_unmount(self) -> None:
        """Close DB connection when the screen is unmounted."""
        self._close_db()

    def _close_db(self) -> None:
        """Close the database connection."""
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None
