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
from dbqm.ui.utils import NavSelect
from textual import work

from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.esqueleto import Esqueleto
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

TYPE_EMOJI = {
    "TABLE": "🗃",
    "VIEW": "👁",
    "PACKAGE": "📦",
    "ROUTINE": "⚙",
}


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
        align: center middle;
        margin-top: 1;
    }
    BrowserScreen #obj-preview-buttons Button {
        margin: 0 1;
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
            with Panel("📂  OBJETOS", id="obj-list-panel"):
                yield NavSelect([], prompt="Selecione a conexao", id="obj-conn")
                yield Select(
                    TYPE_OPTIONS, value="TABLE", allow_blank=False, id="obj-type"
                )
                yield Input(placeholder="Filtrar objetos...", id="obj-filter")
                yield EmptyState(
                    o_que="Objetos",
                    porque="Escolha uma conexao para listar tabelas, views e rotinas",
                    acao_rotulo="Escolher conexao",
                    acao_id="escolher-conexao",
                    id="obj-list-empty",
                )
                # A forma da lista que vem, nao um rodopio: reserva o
                # espaco certo enquanto a conexao busca os objetos. Uma
                # coluna so: `#obj-list` e um OptionList, uma string por
                # linha (`_populate_list`), nao uma tabela de duas colunas.
                yield Esqueleto(linhas=10, colunas=1, id="obj-list-skeleton")
                yield OptionList(id="obj-list")

            with Panel("📋  COLUNAS", id="obj-columns-panel"):
                yield DataTable(id="obj-columns")

            with Panel("🔍  DADOS", accent=True, id="obj-preview-panel"):
                yield ResultTable(id="obj-preview")
                # Fonte de PACKAGE/ROUTINE: conteudo para consumir, nao um
                # formulario de edicao — nao usar o mesmo visual de campo
                # desabilitado (ver `-somente-leitura` em dbqm/ui/theme.py).
                yield SqlViewer("", id="obj-source", classes="-somente-leitura")
                with Horizontal(id="obj-preview-buttons"):
                    yield Button("Extrair DDL", id="obj-ddl")
                    yield Button("Carregar mais", id="obj-more")

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
        skeleton = self.query_one("#obj-list-skeleton", Esqueleto)
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
            self.notify("Nenhuma conexao configurada.", severity="warning")

    def _get_selected_conn(self):
        """Resolve the currently selected connection object."""
        from dbqm.models.connection import find_connection

        conn_name = self.query_one("#obj-conn", Select).value
        if conn_name is Select.BLANK:
            return None
        return find_connection(conn_name)

    # ------------------------------------------------------------------
    # Reactions: connection / type / filter
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
        from dbqm.core.object_browser import list_objects

        conn = self._current_conn
        obj_type = self._obj_type
        if conn is None or not obj_type:
            return

        try:
            if self._db is None:
                self._db = get_connection(conn)
            objects = list_objects(self._db, conn.db_type, obj_type)
            self.app.call_from_thread(self._on_objects_loaded, objects)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, str(e))

    def _on_objects_loaded(self, objects: list[str]) -> None:
        self._objects = objects
        self._update_obj_list_visibility()
        self._populate_list()
        if not objects:
            self.notify("Nenhum objeto encontrado.", severity="warning")

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

        emoji = TYPE_EMOJI.get(self._obj_type, "")
        prefix = f"{emoji}  " if emoji else ""

        option_list = self.query_one("#obj-list", OptionList)
        option_list.clear_options()
        for obj in objects[:500]:
            option_list.add_option(Option(f"{prefix}{obj}", id=obj))

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
            self.app.call_from_thread(self._on_error, f"Estrutura: {e}")

        # First page -> DADOS
        self._preview_offset = 0
        try:
            result = browse_table(
                self._db, conn.db_type, name, conn.name,
                self._preview_limit, 0,
            )
            self.app.call_from_thread(self._on_preview_loaded, result, False)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, f"Dados: {e}")

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
                f"Source nao disponivel para o tipo de banco '{conn.db_type}'.",
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
                message = "; ".join(errors) if errors else "Source nao encontrado."
                self.app.call_from_thread(self._on_source_unavailable, message)
            else:
                source_text = "\n\n".join(o.ddl for o in objs)
                self.app.call_from_thread(self._on_source_loaded, source_text)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, f"Source: {e}")

        # COLUNAS: non-tabular objects get a routine list (PACKAGE) or a note.
        try:
            if obj_type == "PACKAGE":
                from dbqm.core.object_browser import list_package_routines

                pkg_info = list_package_routines(self._db, conn.db_type, name)
                self.app.call_from_thread(self._on_package_routines_loaded, pkg_info)
            else:
                self.app.call_from_thread(
                    self._on_columns_note,
                    "Objeto nao tabular — veja o source ao lado",
                )
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, f"Estrutura: {e}")

    def _on_structure_loaded(self, structure) -> None:
        table = self.query_one("#obj-columns", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column("Coluna", key="col")
        table.add_column("Tipo", key="type")
        table.add_column("Tamanho", key="size")
        table.add_column("Nulo", key="null")
        table.add_column("Chave", key="key")

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
                "Y" if col.nullable else "N", " ".join(key_parts),
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
        table.add_column("Rotina", key="name")
        table.add_column("Tipo", key="rtype")
        table.add_column("Assinatura", key="sig")

        for routine in pkg_info.routines:
            table.add_row(str(routine.name), str(routine.routine_type), routine.signature)

        if not pkg_info.routines:
            self.notify("Nenhuma rotina encontrada no pacote.", severity="warning")

    def _on_columns_note(self, note: str) -> None:
        table = self.query_one("#obj-columns", DataTable)
        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column("Info", key="info")
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
        self.notify(f"Erro: {error}", severity="error", timeout=8)

    # ------------------------------------------------------------------
    # Buttons: Extrair DDL / Carregar mais
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "obj-ddl":
            self._handle_extract_ddl()
        elif btn_id == "obj-more":
            self._handle_load_more()
        elif btn_id == "escolher-conexao":
            self.query_one("#obj-conn", Select).focus()

    def _handle_extract_ddl(self) -> None:
        if not self._selected_object or self._current_conn is None:
            self.notify("Selecione um objeto.", severity="warning")
            return
        conn = self._current_conn
        self.notify(f"Extraindo DDL de {self._selected_object}...")
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
            elif conn.db_type in ("postgresql", "mysql"):
                result = self._extract_generic(conn, obj_name)
            else:
                self.app.call_from_thread(
                    self._on_error,
                    f"Tipo de banco '{conn.db_type}' nao suportado para DDL.",
                )
                return

            if result.errors and not result.objects:
                self.app.call_from_thread(self._on_error, "; ".join(result.errors))
                return

            dir_path, _ = save_extraction(result)
            self.app.call_from_thread(self._on_ddl_saved, dir_path, result.saved_files)
        except Exception as e:  # pragma: no cover - depends on live DB
            self.app.call_from_thread(self._on_error, str(e))

    def _extract_generic(self, conn, object_name: str):
        """Extract DDL for PostgreSQL/MySQL objects (own short-lived handle)."""
        from dbqm.core.db_manager import get_connection
        from dbqm.core.ddl_extractor import ExtractionResult

        db = None
        try:
            db = get_connection(conn)
            result = ExtractionResult(
                object_name=object_name, object_type="UNKNOWN",
                owner="", connection_name=conn.name,
            )
            if conn.db_type == "postgresql":
                from dbqm.core.ddl_pg import extract_pg_ddl
                extract_pg_ddl(db, object_name, result)
            else:
                from dbqm.core.ddl_mysql import extract_mysql_ddl
                extract_mysql_ddl(db, object_name, result)
            return result
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    def _on_ddl_saved(self, dir_path: str, saved_files: list[str]) -> None:
        if saved_files:
            self.notify(
                f"DDL salvo: {', '.join(saved_files)} em {dir_path}", timeout=6
            )
        else:
            self.notify(f"DDL salvo em {dir_path}", timeout=6)

    def _handle_load_more(self) -> None:
        if not self._selected_object or self._current_conn is None:
            return
        next_offset = self._preview_offset + self._preview_limit
        if self._preview_total and next_offset >= self._preview_total:
            self.notify("Nao ha mais registros.", severity="information")
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
            self.app.call_from_thread(self._on_error, f"Dados: {e}")

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
