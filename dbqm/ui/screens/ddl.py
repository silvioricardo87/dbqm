"""DDL extraction screen — extract and view database object DDL."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Select, Static
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.progress import ProgressIndicator
from dbqm.ui.widgets.sql_viewer import SqlViewer


class DDLScreen(Vertical):
    """Screen widget for extracting DDL from database objects.

    Phase 1 — connection selector + object name input + extract button.
    Phase 2 — extraction result displayed in SqlViewer.
    """

    DEFAULT_CSS = """
    DDLScreen {
        height: 1fr;
    }
    DDLScreen #ddl-input-phase {
        height: auto;
        padding: 1;
    }
    DDLScreen #ddl-conn-bar {
        height: auto;
        padding: 0 0 1 0;
    }
    DDLScreen #ddl-conn-bar Select {
        width: 1fr;
    }
    DDLScreen #ddl-object-bar {
        height: auto;
        padding: 0 0 1 0;
    }
    DDLScreen #ddl-object-bar Input {
        width: 1fr;
    }
    DDLScreen #ddl-btn-bar {
        height: auto;
        align: center middle;
    }
    DDLScreen #ddl-btn-bar Button {
        margin: 0 1;
    }
    DDLScreen #ddl-results-phase {
        height: 1fr;
        padding: 0 1;
    }
    DDLScreen #ddl-result-info {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    DDLScreen #ddl-details {
        height: auto;
        padding: 0 1;
    }
    DDLScreen #ddl-sql-viewer {
        height: 1fr;
        max-height: 100%;
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
        self._object_name = ""
        self._extraction_result = None
        self._output_dir = ""
        self._next_file_num = 0

    def compose(self) -> ComposeResult:
        # Input phase
        with Vertical(id="ddl-input-phase"):
            with Horizontal(id="ddl-conn-bar"):
                yield Select([], prompt="Selecione a conexao", id="ddl-conn-select")
            with Horizontal(id="ddl-object-bar"):
                yield Input(
                    placeholder="Nome do objeto (ex: tabela, view, package, package.rotina)",
                    id="ddl-object-input",
                )
            with Horizontal(id="ddl-btn-bar"):
                yield Button("Extrair", variant="primary", id="ddl-extract")

        # Progress indicator
        yield ProgressIndicator()

        # Results phase (hidden initially)
        with Vertical(id="ddl-results-phase"):
            yield Static("", id="ddl-result-info")
            yield Static("", id="ddl-details")
            yield SqlViewer("", id="ddl-sql-viewer")

    def on_mount(self) -> None:
        self.query_one("#ddl-results-phase").display = False
        self._load_connections()

    def _load_connections(self) -> None:
        """Load supported connections into the Select widget."""
        from dbqm.models.connection import load_connections

        connections = load_connections()
        supported = [c for c in connections if c.db_type in ("oracle", "postgresql", "mysql")]
        options = [
            (f"{c.name} ({c.db_type} - {c.display_target()})", c.name)
            for c in supported
        ]

        select_widget = self.query_one("#ddl-conn-select", Select)
        select_widget.set_options(options)

        if not supported:
            self.notify(
                "Nenhuma conexao Oracle, PostgreSQL ou MySQL configurada.",
                severity="warning",
            )

    def _get_selected_conn(self):
        """Get the currently selected connection object."""
        from dbqm.models.connection import find_connection

        select_widget = self.query_one("#ddl-conn-select", Select)
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
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""

        if btn_id == "ddl-extract":
            self._handle_extract()
        elif btn_id == "ddl-extract-deps":
            self._handle_extract_deps()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Allow pressing Enter in the object input to trigger extraction."""
        if event.input.id == "ddl-object-input":
            self._handle_extract()

    def _handle_extract(self) -> None:
        """Start DDL extraction."""
        conn = self._get_selected_conn()
        if not conn:
            return

        obj_input = self.query_one("#ddl-object-input", Input).value.strip()
        if not obj_input:
            self.notify("Informe o nome do objeto.", severity="warning")
            return

        self._current_conn = conn
        self._object_name = obj_input

        self.query_one(ProgressIndicator).start(
            f"Extraindo DDL de [bold]{obj_input}[/] em [bold]{conn.name}[/]..."
        )
        self._run_extraction(conn, obj_input)

    @work(thread=True)
    def _run_extraction(self, conn, obj_input: str) -> None:
        """Run DDL extraction in a background thread."""
        from dbqm.core.ddl_extractor import (
            extract_ddl,
            save_extraction,
            extract_routine,
            save_routine_extraction,
        )

        try:
            if conn.db_type == "oracle":
                obj_upper = obj_input.upper()
                if "." in obj_upper:
                    # Package.routine extraction
                    pkg_name, routine_name = obj_upper.split(".", 1)
                    result = extract_routine(conn, pkg_name, routine_name)
                    if result.errors and not result.body_routines:
                        self.call_from_thread(self._on_extraction_error, result.errors)
                        return
                    dir_path, next_num = save_routine_extraction(result)
                    # Build combined DDL text for display
                    ddl_parts = []
                    for obj in result.spec_headers:
                        ddl_parts.append(f"-- {obj.obj_type}: {obj.name}\n{obj.ddl}")
                    for obj in result.body_routines:
                        ddl_parts.append(f"-- {obj.obj_type}: {obj.name}\n{obj.ddl}")
                    combined_ddl = "\n\n".join(ddl_parts)
                    info = (
                        f"Package: {result.owner}.{result.package_name} | "
                        f"Rotina: {result.routine_name} | {conn.name}"
                    )
                    deps = result.dependencies
                    files = result.saved_files
                    errors = result.errors
                    self.call_from_thread(
                        self._on_extraction_result,
                        combined_ddl, info, dir_path, next_num, deps, files, errors,
                    )
                    return
                else:
                    result = extract_ddl(conn, obj_upper)
            elif conn.db_type in ("postgresql", "mysql"):
                result = self._extract_generic(conn, obj_input)
            else:
                self.call_from_thread(
                    self._on_extraction_error,
                    [f"Tipo de banco '{conn.db_type}' nao suportado para DDL."],
                )
                return

            if result.errors and not result.objects:
                self.call_from_thread(self._on_extraction_error, result.errors)
                return

            dir_path, next_num = save_extraction(result)

            # Build combined DDL text
            ddl_parts = []
            for obj in result.objects:
                ddl_parts.append(f"-- {obj.obj_type}: {obj.name}\n{obj.ddl}")
            combined_ddl = "\n\n".join(ddl_parts)

            info = (
                f"Objeto: {result.owner}.{result.object_name} | "
                f"Tipo: {result.object_type} | {result.connection_name}"
            )
            self.call_from_thread(
                self._on_extraction_result,
                combined_ddl, info, dir_path, next_num,
                result.dependencies, result.saved_files, result.errors,
            )

        except Exception as e:
            self.call_from_thread(self._on_extraction_error, [str(e)])

    def _extract_generic(self, conn, object_name: str):
        """Extract DDL for PostgreSQL/MySQL objects."""
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

    def _on_extraction_error(self, errors: list[str]) -> None:
        """Handle extraction errors."""
        self.query_one(ProgressIndicator).stop()
        for err in errors:
            self.notify(f"Erro: {err}", severity="error", timeout=8)

    def _on_extraction_result(
        self,
        ddl: str,
        info: str,
        dir_path: str,
        next_num: int,
        dependencies: list[str],
        saved_files: list[str],
        errors: list[str],
    ) -> None:
        """Handle successful extraction result."""
        self.query_one(ProgressIndicator).stop()

        self._output_dir = dir_path
        self._next_file_num = next_num
        self._dependencies = dependencies

        # Switch to results phase
        self.query_one("#ddl-input-phase").display = False
        results_phase = self.query_one("#ddl-results-phase")
        results_phase.display = True

        # Update info bar
        info_widget = self.query_one("#ddl-result-info", Static)
        info_widget.update(f"[bold]{info}[/]")

        # Build details text
        details_parts = []
        if saved_files:
            details_parts.append(f"Arquivos: {', '.join(saved_files)}")
        if dependencies:
            details_parts.append(f"Dependencias: {len(dependencies)}")
        if errors:
            for err in errors:
                details_parts.append(f"[yellow]Aviso: {err}[/yellow]")
        details_parts.append(f"Diretorio: {dir_path}")

        details_widget = self.query_one("#ddl-details", Static)
        details_widget.update("\n".join(details_parts))

        # Show DDL in viewer
        sql_viewer = self.query_one("#ddl-sql-viewer", SqlViewer)
        sql_viewer.set_sql(ddl)

        # Set up action bar
        actions = [
            Action("Exportar", "E", "ddl_export"),
        ]
        if dependencies:
            actions.append(Action("Extrair Deps", "D", "ddl_extract_deps"))
        actions.append(Action("Voltar", "Esc", "ddl_go_back"))

        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Extract dependencies
    # ------------------------------------------------------------------

    def _handle_extract_deps(self) -> None:
        """Extract dependencies DDL."""
        if not hasattr(self, '_dependencies') or not self._dependencies:
            self.notify("Nenhuma dependencia para extrair.", severity="warning")
            return

        self.query_one(ProgressIndicator).start("Extraindo dependencias...")
        self._run_deps_extraction(
            self._current_conn, self._dependencies,
            self._object_name, self._output_dir, self._next_file_num,
        )

    @work(thread=True)
    def _run_deps_extraction(
        self, conn, dependencies: list[str],
        parent_name: str, output_dir: str, file_num: int,
    ) -> None:
        """Run dependency extraction in background."""
        from dbqm.core.ddl_extractor import (
            extract_dependencies_ddl, save_dependencies_extraction,
        )

        try:
            dep_result = extract_dependencies_ddl(conn, dependencies, parent_name)

            if not dep_result.objects:
                self.call_from_thread(
                    self._on_deps_error, "Nenhuma dependencia pode ser extraida."
                )
                return

            dep_filepath = save_dependencies_extraction(dep_result, output_dir, file_num)

            # Build DDL text for deps
            ddl_parts = []
            for obj in dep_result.objects:
                ddl_parts.append(f"-- {obj.obj_type}: {obj.name}\n{obj.ddl}")
            combined = "\n\n".join(ddl_parts)

            self.call_from_thread(self._on_deps_result, combined, dep_filepath, dep_result.errors)

        except Exception as e:
            self.call_from_thread(self._on_deps_error, str(e))

    def _on_deps_error(self, error: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro: {error}", severity="error", timeout=8)

    def _on_deps_result(self, ddl: str, filepath: str, errors: list[str]) -> None:
        self.query_one(ProgressIndicator).stop()

        # Append deps DDL to the viewer
        sql_viewer = self.query_one("#ddl-sql-viewer", SqlViewer)
        current = sql_viewer._sql
        sql_viewer.set_sql(current + "\n\n-- DEPENDENCIAS\n\n" + ddl)

        self.notify(f"Dependencias salvas: {filepath}", timeout=5)
        if errors:
            for err in errors:
                self.notify(f"Aviso: {err}", severity="warning", timeout=5)

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "ddl_export":
            self._handle_ddl_export()
        elif action == "ddl_extract_deps":
            self._handle_extract_deps()
        elif action == "ddl_go_back":
            self.go_back_to_input()

    def _handle_ddl_export(self) -> None:
        """Export the displayed DDL to a .sql file."""
        from dbqm.core.exporter import export_sql_file

        try:
            sql_viewer = self.query_one("#ddl-sql-viewer", SqlViewer)
            ddl = sql_viewer._sql
            label = self._object_name or "ddl"
            path = export_sql_file(ddl, label)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    def go_back_to_input(self) -> None:
        """Return to the input phase."""
        self.query_one("#ddl-input-phase").display = True
        self.query_one("#ddl-results-phase").display = False
        self._extraction_result = None

        try:
            self.app.query_one(ActionBar).set_actions([])
        except Exception:
            pass
