"""Object browser screen — three live panels: objects, columns, data preview.

Selecting an object in the OBJETOS list fires a single worker that fills the
COLUNAS structure table and the DADOS preview simultaneously — no wizard steps.
The DDL extraction (previously a standalone screen) is folded in here as the
"Extrair DDL" button in the DADOS panel.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Input, OptionList, Select
from textual.widgets.option_list import Option
from dbqm.i18n import t
from dbqm.ui.utils import NavSelect
from textual import work

from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.skeleton import Skeleton
from dbqm.ui.widgets.hierarchical_list import hierarchical_item
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.result_table import ResultTable
from dbqm.ui.widgets.sql_viewer import SqlViewer

DEFAULT_LIMIT = 100

# Object types that are shown as inline SOURCE text (no tabular DADOS).
SOURCE_TYPES = ("PACKAGE", "ROUTINE")

TYPE_OPTIONS = [
    ("Tabelas", "TABLE"),
    ("Views", "VIEW"),
    ("Packages", "PACKAGE"),
    ("Rotinas", "ROUTINE"),
]


class BrowserScreen(Vertical):
    """Screen widget for browsing database objects as three live panels.

    OBJETOS  — connection + type selects, a filter, and the object list.
    COLUNAS  — the selected object's structure (columns).
    DADOS    — a paginated preview of the object's rows + DDL extraction.
    """

    DEFAULT_CSS = """
    BrowserScreen {
        height: 1fr;
    }
    BrowserScreen #browser-body {
        height: 1fr;
    }
    BrowserScreen #obj-list-panel {
        width: 46;
    }
    BrowserScreen #obj-columns-panel {
        width: 1fr;
    }
    BrowserScreen #obj-preview-panel {
        width: 1fr;
    }
    BrowserScreen #obj-conn {
        width: 100%;
    }
    BrowserScreen #obj-type {
        width: 100%;
        margin-top: 1;
    }
    BrowserScreen #obj-filter {
        width: 100%;
        margin-top: 1;
    }
    BrowserScreen #obj-list {
        height: 1fr;
        margin-top: 1;
    }
    BrowserScreen #obj-list-empty {
        height: 1fr;
    }
    BrowserScreen #obj-list-skeleton {
        display: none;
        margin-top: 1;
    }
    BrowserScreen #obj-columns {
        height: 1fr;
    }
    BrowserScreen #obj-preview {
        height: 1fr;
    }
    BrowserScreen #obj-source {
        height: 1fr;
        max-height: 100%;
    }
    BrowserScreen #obj-preview-buttons {
        height: auto;
        margin-top: 1;
        /* Ancorado a esquerda, sob o codigo-fonte do objeto que estes
           dois botoes operam (secao 7 da gramatica). */
    }
    BrowserScreen #obj-preview-buttons Button {
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
        self._db = None
        self._obj_type = "TABLE"
        self._objects: list[str] = []
        self._selected_object = ""
        self._preview_limit = DEFAULT_LIMIT
        self._preview_offset = 0
        self._preview_columns: list[str] = []
        self._preview_rows: list[list] = []
        self._preview_total = 0

    def compose(self) -> ComposeResult:
        with Horizontal(id="browser-body"):
            with Panel(t("panel.objects"), id="obj-list-panel"):
                yield NavSelect([], prompt=t("adhoc.select_connection"), id="obj-conn")
                yield Select(
                    TYPE_OPTIONS, value="TABLE", allow_blank=False, id="obj-type"
                )
                yield Input(placeholder=t("browser.filter_placeholder"), id="obj-filter")
                yield EmptyState(
                    what=t("browser.objects_title"),
                    why=t("browser.empty_why"),
                    action_label=t("browser.choose_connection"),
                    action_id="choose-connection",
                    id="obj-list-empty",
                )
                # The shape of the list that is coming, not a spinner: it
                # reserves the right space while the connection fetches the
                # objects. One column only: `#obj-list` is an OptionList,
                # one string per line (`_populate_list`), not a two-column
                # table.
                yield Skeleton(rows=10, columns=1, id="obj-list-skeleton")
                yield OptionList(id="obj-list")

            with Panel(t("panel.columns"), id="obj-columns-panel"):
                yield DataTable(id="obj-columns")

            with Panel(t("panel.data"), accent=True, id="obj-preview-panel"):
                yield ResultTable(id="obj-preview")
                # PACKAGE/ROUTINE source: content to consume, not an
                # editing form — do not use the same look as a disabled
                # field (see `-read-only` in dbqm/ui/theme.py).
                yield SqlViewer("", id="obj-source", classes="-read-only")
                with Horizontal(id="obj-preview-buttons"):
                    yield Button(t("browser.extract_ddl"), id="obj-ddl")
                    yield Button(t("browser.load_more"), id="obj-more")

    def on_mount(self) -> None:
        columns = self.query_one("#obj-columns", DataTable)
        columns.cursor_type = "row"
        self._show_table_view()
        self._load_connections()
        self._update_obj_list_visibility()
        self.call_after_refresh(self._set_initial_focus)

    def _update_obj_list_visibility(self, *, loading: bool = False) -> None:
        """Switch the OBJETOS panel between its three states: pick a
        connection (empty state), the object list, or — while
        `_reload_objects` runs — the skeleton with the shape of the list
        that is coming."""
        empty = self.query_one("#obj-list-empty", EmptyState)
        option_list = self.query_one("#obj-list", OptionList)
        skeleton = self.query_one("#obj-list-skeleton", Skeleton)
        has_conn = self._current_conn is not None
        skeleton.display = loading
        empty.display = not has_conn and not loading
        option_list.display = has_conn and not loading

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#obj-conn", Select).focus()
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
        self.query_one("#obj-conn", Select).set_options(options)

        if not connections:
            self.notify(t("connection.none_configured"), severity="warning")

    def _get_selected_conn(self):
        """Resolve the currently selected connection object."""
        from dbqm.models.connection import find_connection

        conn_name = self.query_one("#obj-conn", Select).value
        if conn_name is Select.BLANK:
            return None
        return find_connection(conn_name)

    # ------------------------------------------------------------------
    # Reacts to changes on the connection, type and filter selectors.
    # ------------------------------------------------------------------

    def on_select_changed(self, event: Select.Changed) -> None:
        sel_id = event.select.id or ""
        if sel_id == "obj-conn":
            conn = self._get_selected_conn()
            # Switching connection invalidates the open handle.
            self._close_db()
            self._current_conn = conn
            if conn is not None:
                self._update_obj_list_visibility(loading=True)
                self._reload_objects()
            else:
                self._update_obj_list_visibility()
        elif sel_id == "obj-type":
            value = event.value
            self._obj_type = "" if value is Select.BLANK else str(value)
            if self._current_conn is not None and self._obj_type:
                self._update_obj_list_visibility(loading=True)
                self._reload_objects()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "obj-filter":
            # Filter the already-loaded list client-side (responsive, no DB hit).
            self._populate_list()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "obj-filter":
            self._populate_list()

    # ------------------------------------------------------------------
    # Object listing
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True)
    def _reload_objects(self):
        """Fetch the object list for the current connection + type."""
        from dbqm.core.db_manager import get_connection
        from dbqm.core.object_browser import UnsupportedEngine, list_objects

        conn = self._current_conn
        obj_type = self._obj_type
        if conn is None or not obj_type:
            return

        try:
            if self._db is None:
                self._db = get_connection(conn)
            objects = list_objects(self._db, conn.db_type, obj_type)
            self.app.call_from_thread(self._on_objects_loaded, objects)
        except UnsupportedEngine as e:
            # The engine has no such object type at all. That is an empty
            # list with an explanation, not an error state: `_on_error`
            # leaves `self._objects` untouched, so the previous type's
            # objects would stay on screen under the new type's label.
            self.app.call_from_thread(self._on_unsupported_type, str(e))
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, str(e))

    def _on_objects_loaded(self, objects: list[str]) -> None:
        self._objects = objects
        self._update_obj_list_visibility()
        self._populate_list()
        if not objects:
            self.notify(t("browser.no_objects"), severity="warning")

    def _on_unsupported_type(self, mensagem: str) -> None:
        """Clear the list, then say why it is empty.

        `core` raises for a type the engine does not have, where it used to
        return an empty list. Clearing first is what keeps the screen honest.
        """
        self._objects = []
        self._update_obj_list_visibility()
        self._populate_list()
        self.notify(mensagem, severity="warning", timeout=8)

    def _populate_list(self) -> None:
        """Render the cached object list, applying the current text filter."""
        try:
            filter_text = self.query_one("#obj-filter", Input).value.strip().upper()
        except Exception:
            filter_text = ""

        if filter_text:
            objects = [o for o in self._objects if filter_text in o.upper()]
        else:
            objects = self._objects

        # Identity only, no disambiguation: the type `Select` above is
        # `allow_blank=False` (always a valid TYPE_OPTIONS selected), so
        # every row visible here is always of the SAME type — writing the
        # type out in full on each item would repeat what the filter has
        # already fixed, taking up one line per object without really
        # disambiguating anything. And with no context either:
        # `list_objects` does not return owner, row count or any other
        # per-object metadata (only the name) — inventing a third field
        # here would be the mechanical mapping this component exists to
        # avoid.
        option_list = self.query_one("#obj-list", OptionList)
        option_list.clear_options()
        for obj in objects[:500]:
            option_list.add_option(Option(hierarchical_item(obj), id=obj))

    def on_option_list_option_selected(
        self, event: OptionList.OptionSelected
    ) -> None:
        if event.option_list.id != "obj-list":
            return
        name = str(event.option.id) if event.option.id else None
        if not name:
            return
        self._selected_object = name
        self._load_object(name)

    # ------------------------------------------------------------------
    # Live load: structure + preview together
    # ------------------------------------------------------------------

    @work(thread=True, exclusive=True, group="obj-load")
    def _load_object(self, name: str):
        """Fill COLUNAS (structure) and DADOS (first page) in one worker.

        TABLE/VIEW keep the tabular structure + preview flow. PACKAGE/ROUTINE
        have no rows to preview, so DADOS shows the object SOURCE instead —
        calling browse_table on them is a guaranteed ORA-00942.
        """
        conn = self._current_conn
        obj_type = self._obj_type
        if conn is None or self._db is None:
            return

        self._selected_object = name

        if obj_type in SOURCE_TYPES:
            self._load_object_source(conn, name, obj_type)
            return

        from dbqm.core.object_browser import get_table_structure
        from dbqm.core.table_browser import browse_table

        self.app.call_from_thread(self._show_table_view)

        # Structure -> COLUNAS
        try:
            structure = get_table_structure(self._db, conn.db_type, name)
            self.app.call_from_thread(self._on_structure_loaded, structure)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, t("browser.structure_failed", error=e))

        # First page -> DADOS
        self._preview_offset = 0
        try:
            result = browse_table(
                self._db, conn.db_type, name, conn.name,
                self._preview_limit, 0,
            )
            self.app.call_from_thread(self._on_preview_loaded, result, False)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, t("browser.data_failed", error=e))

    def _load_object_source(self, conn, name: str, obj_type: str) -> None:
        """Fetch SOURCE text for a PACKAGE/ROUTINE and show it in DADOS.

        Reuses the same extraction core the "Extrair DDL" button calls
        (dbqm.core.ddl_extractor), capturing the DDL text instead of only
        saving it to disk.
        """
        self.app.call_from_thread(self._show_source_view)

        if conn.db_type != "oracle":
            self.app.call_from_thread(
                self._on_source_unavailable,
                t("browser.source_unavailable", type=conn.db_type),
            )
            return

        from dbqm.core.ddl_extractor import extract_ddl, extract_routine

        try:
            errors: list[str] = []
            if obj_type == "ROUTINE" and "." in name:
                pkg_name, routine_name = name.upper().split(".", 1)
                result = extract_routine(conn, pkg_name, routine_name)
                objs = list(result.spec_headers) + list(result.body_routines)
                errors = result.errors
            else:
                result = extract_ddl(conn, name)
                objs = list(result.objects)
                errors = result.errors

            if not objs:
                message = "; ".join(errors) if errors else t("browser.source_not_found")
                self.app.call_from_thread(self._on_source_unavailable, message)
            else:
                source_text = "\n\n".join(o.ddl for o in objs)
                self.app.call_from_thread(self._on_source_loaded, source_text)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, t("browser.source_failed", error=e))

        # COLUNAS: non-tabular objects get a routine list (PACKAGE) or a note.
        try:
            if obj_type == "PACKAGE":
                from dbqm.core.object_browser import list_package_routines

                pkg_info = list_package_routines(self._db, conn.db_type, name)
                self.app.call_from_thread(self._on_package_routines_loaded, pkg_info)
            else:
                self.app.call_from_thread(
                    self._on_columns_note,
                    t("browser.not_tabular"),
                )
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, t("browser.structure_failed", error=e))

    def _on_structure_loaded(self, structure) -> None:
        table = self.query_one("#obj-columns", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column(t("common.column"), key="col")
        table.add_column(t("common.type"), key="type")
        table.add_column(t("browser.column_size"), key="size")
        table.add_column(t("common.nullable"), key="null")
        table.add_column(t("common.key"), key="key")

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

            table.add_row(
                str(col.name), str(col.data_type), str(size),
                t("common.yes_initial") if col.nullable else t("common.no_initial"),
                " ".join(key_parts),
            )

    def _on_preview_loaded(self, result, append: bool) -> None:
        from dbqm.core.query_engine import QueryResult

        self._preview_total = result.total_count
        self._preview_columns = result.columns
        if append:
            self._preview_rows.extend(result.rows)
        else:
            self._preview_rows = list(result.rows)
        self._preview_offset = result.offset

        qr = QueryResult(
            query_name=f"Dados: {self._selected_object}",
            connection_name=result.connection_name,
            columns=self._preview_columns,
            rows=self._preview_rows,
            row_count=len(self._preview_rows),
            elapsed=result.elapsed,
        )
        self.query_one("#obj-preview", ResultTable).load_result(qr)

    def _on_source_loaded(self, source_text: str) -> None:
        self.query_one("#obj-source", SqlViewer).set_sql(source_text)

    def _on_source_unavailable(self, message: str) -> None:
        self.query_one("#obj-source", SqlViewer).set_sql(f"-- {message}")
        self.notify(message, severity="warning")

    def _on_package_routines_loaded(self, pkg_info) -> None:
        table = self.query_one("#obj-columns", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column(t("browser.column_routine"), key="name")
        table.add_column(t("common.type"), key="rtype")
        table.add_column(t("browser.column_signature"), key="sig")

        for routine in pkg_info.routines:
            table.add_row(str(routine.name), str(routine.routine_type), routine.signature)

        if not pkg_info.routines:
            self.notify(t("browser.no_routines_in_package"), severity="warning")

    def _on_columns_note(self, note: str) -> None:
        table = self.query_one("#obj-columns", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column(t("browser.column_info"), key="info")
        table.add_row(note)

    def _show_table_view(self) -> None:
        """Show the tabular DADOS preview (TABLE/VIEW) and hide the source view."""
        self.query_one("#obj-preview", ResultTable).display = True
        self.query_one("#obj-source", SqlViewer).display = False
        self.query_one("#obj-more", Button).display = True

    def _show_source_view(self) -> None:
        """Show the read-only SOURCE view (PACKAGE/ROUTINE) and hide the table."""
        self.query_one("#obj-preview", ResultTable).display = False
        self.query_one("#obj-source", SqlViewer).display = True
        self.query_one("#obj-more", Button).display = False

    def _on_error(self, error: str) -> None:
        # Shared handler for object-list/structure/preview/DDL errors: only
        # the first of those leaves the skeleton up, but resetting here is
        # a harmless no-op for the other three (idempotent on `has_conn`).
        self._update_obj_list_visibility()
        self.notify(t("adhoc.error", error=error), severity="error", timeout=8)

    # ------------------------------------------------------------------
    # Buttons: Extrair DDL / Carregar mais
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "obj-ddl":
            self._handle_extract_ddl()
        elif btn_id == "obj-more":
            self._handle_load_more()
        elif btn_id == "choose-connection":
            self.query_one("#obj-conn", Select).focus()

    def _handle_extract_ddl(self) -> None:
        if not self._selected_object or self._current_conn is None:
            self.notify(t("browser.select_object"), severity="warning")
            return
        conn = self._current_conn
        self.notify(t("browser.extracting", name=self._selected_object))
        self._run_ddl(conn, self._selected_object)

    @work(thread=True, group="obj-ddl")
    def _run_ddl(self, conn, obj_name: str):
        """Extract DDL via the same core path the standalone DDL screen used."""
        from dbqm.core.ddl_extractor import (
            extract_ddl,
            save_extraction,
            extract_routine,
            save_routine_extraction,
        )

        try:
            if conn.db_type == "oracle":
                obj_upper = obj_name.upper()
                if "." in obj_upper:
                    pkg_name, routine_name = obj_upper.split(".", 1)
                    result = extract_routine(conn, pkg_name, routine_name)
                    if result.errors and not result.body_routines:
                        self.app.call_from_thread(self._on_error, "; ".join(result.errors))
                        return
                    dir_path, _ = save_routine_extraction(result)
                    self.app.call_from_thread(self._on_ddl_saved, dir_path, result.saved_files)
                    return
                result = extract_ddl(conn, obj_upper)
            else:
                # `extract_ddl` dispatches by engine (sqlite, postgresql,
                # mysql) and answers SQL Server with an error in `errors`;
                # the screen used to keep its own copy of that routing, which
                # is how SQLite arrived here unsupported and SQL Server was
                # once handed to the MySQL extractor.
                result = extract_ddl(conn, obj_name)

            if result.errors and not result.objects:
                self.app.call_from_thread(self._on_error, "; ".join(result.errors))
                return

            dir_path, _ = save_extraction(result)
            self.app.call_from_thread(self._on_ddl_saved, dir_path, result.saved_files)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, str(e))

    def _on_ddl_saved(self, dir_path: str, saved_files: list[str]) -> None:
        if saved_files:
            self.notify(
                t("browser.ddl_saved_files", files=", ".join(saved_files), folder=dir_path), timeout=6
            )
        else:
            self.notify(t("browser.ddl_saved", folder=dir_path), timeout=6)

    def _handle_load_more(self) -> None:
        if not self._selected_object or self._current_conn is None:
            return
        next_offset = self._preview_offset + self._preview_limit
        if self._preview_total and next_offset >= self._preview_total:
            self.notify(t("browser.no_more_rows"), severity="information")
            return
        self._load_more_page(next_offset)

    @work(thread=True, group="obj-more")
    def _load_more_page(self, offset: int):
        from dbqm.core.table_browser import browse_table

        conn = self._current_conn
        if conn is None or self._db is None:
            return
        try:
            result = browse_table(
                self._db, conn.db_type, self._selected_object, conn.name,
                self._preview_limit, offset,
            )
            self.app.call_from_thread(self._on_preview_loaded, result, True)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, t("browser.data_failed", error=e))

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def on_unmount(self) -> None:
        self._close_db()

    def _close_db(self) -> None:
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None
