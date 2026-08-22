"""Package editor screen — create, edit, and compile Oracle packages."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static, TextArea
from textual import work

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.progress import ProgressIndicator


# ======================================================================
# Modals
# ======================================================================


class _PackageChoiceModal(ModalScreen[str | None]):
    """Choose between editing an existing package or creating a new one."""

    DEFAULT_CSS = """
    _PackageChoiceModal {
        align: center middle;
    }
    _PackageChoiceModal #pkg-choice-dialog {
        width: 50;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _PackageChoiceModal #pkg-choice-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _PackageChoiceModal #pkg-choice-buttons {
        width: 100%;
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    _PackageChoiceModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="pkg-choice-dialog"):
            yield Static("Package Editor", id="pkg-choice-title")
            with Horizontal(id="pkg-choice-buttons"):
                yield Button("Editar existente", variant="primary", id="pkg-choice-edit")
                yield Button("Criar novo", variant="default", id="pkg-choice-new")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pkg-choice-edit":
            self.dismiss("edit")
        elif event.button.id == "pkg-choice-new":
            self.dismiss("new")

    def action_cancel(self) -> None:
        self.dismiss(None)


class _PackageSearchModal(ModalScreen[dict | None]):
    """Search for an existing package by connection and name."""

    DEFAULT_CSS = """
    _PackageSearchModal {
        align: center middle;
    }
    _PackageSearchModal #pkg-search-dialog {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _PackageSearchModal #pkg-search-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _PackageSearchModal .pkg-search-row {
        height: auto;
        padding: 0 0 1 0;
    }
    _PackageSearchModal .pkg-search-row Select {
        width: 1fr;
    }
    _PackageSearchModal .pkg-search-row Input {
        width: 1fr;
    }
    _PackageSearchModal #pkg-search-buttons {
        width: 100%;
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    _PackageSearchModal #pkg-search-error {
        height: auto;
        color: $error;
        padding: 0 0 1 0;
    }
    _PackageSearchModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="pkg-search-dialog"):
            yield Static("Buscar Package", id="pkg-search-title")
            with Horizontal(classes="pkg-search-row"):
                yield Select([], prompt="Selecione a conexao Oracle", id="pkg-search-conn")
            with Horizontal(classes="pkg-search-row"):
                yield Input(placeholder="Nome do package", id="pkg-search-name")
            yield Static("", id="pkg-search-error")
            yield ProgressIndicator()
            with Horizontal(id="pkg-search-buttons"):
                yield Button("Buscar", variant="primary", id="pkg-search-go")
                yield Button("Cancelar", variant="default", id="pkg-search-cancel")

    def on_mount(self) -> None:
        self._load_oracle_connections()
        self.query_one("#pkg-search-error").display = False

    def _load_oracle_connections(self) -> None:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        oracle_conns = [c for c in connections if c.db_type == "oracle"]
        options = [
            (f"{c.name} ({c.display_target()})", c.name)
            for c in oracle_conns
        ]
        self.query_one("#pkg-search-conn", Select).set_options(options)

        if not oracle_conns:
            self.query_one("#pkg-search-error", Static).update(
                "Nenhuma conexao Oracle configurada."
            )
            self.query_one("#pkg-search-error").display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pkg-search-go":
            self._handle_search()
        elif event.button.id == "pkg-search-cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "pkg-search-name":
            self._handle_search()

    def _handle_search(self) -> None:
        select = self.query_one("#pkg-search-conn", Select)
        conn_name = select.value
        if conn_name is Select.BLANK:
            self.query_one("#pkg-search-error", Static).update("Selecione uma conexao.")
            self.query_one("#pkg-search-error").display = True
            return

        pkg_name = self.query_one("#pkg-search-name", Input).value.strip()
        if not pkg_name:
            self.query_one("#pkg-search-error", Static).update("Informe o nome do package.")
            self.query_one("#pkg-search-error").display = True
            return

        self.query_one("#pkg-search-error").display = False
        self.query_one(ProgressIndicator).start("Buscando package...")
        self._run_search(conn_name, pkg_name)

    @work(thread=True)
    def _run_search(self, conn_name: str, pkg_name: str) -> None:
        from dbqm.models.connection import find_connection
        from dbqm.core.db_manager import get_connection
        from dbqm.core.package_editor import check_package_exists, fetch_package_source

        try:
            conn = find_connection(conn_name)
            if not conn:
                self.app.call_from_thread(self._on_search_error, "Conexao nao encontrada.")
                return

            db = get_connection(conn)
            try:
                if not check_package_exists(db, pkg_name):
                    self.app.call_from_thread(
                        self._on_search_error,
                        f"Package '{pkg_name.upper()}' nao encontrado.",
                    )
                    return

                spec, body = fetch_package_source(db, pkg_name)
                self.app.call_from_thread(
                    self._on_search_result,
                    conn_name, pkg_name.upper(), spec, body,
                )
            finally:
                db.close()
        except Exception as e:
            self.app.call_from_thread(self._on_search_error, str(e))

    def _on_search_error(self, msg: str) -> None:
        self.query_one(ProgressIndicator).stop()
        self.query_one("#pkg-search-error", Static).update(msg)
        self.query_one("#pkg-search-error").display = True

    def _on_search_result(
        self, conn_name: str, pkg_name: str, spec: str, body: str
    ) -> None:
        self.query_one(ProgressIndicator).stop()
        self.dismiss({
            "conn_name": conn_name,
            "pkg_name": pkg_name,
            "spec": spec,
            "body": body,
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


class _PackageCreateModal(ModalScreen[dict | None]):
    """Create a new package with connection, name, and mode selection."""

    DEFAULT_CSS = """
    _PackageCreateModal {
        align: center middle;
    }
    _PackageCreateModal #pkg-create-dialog {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _PackageCreateModal #pkg-create-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _PackageCreateModal .pkg-create-row {
        height: auto;
        padding: 0 0 1 0;
    }
    _PackageCreateModal .pkg-create-row Select {
        width: 1fr;
    }
    _PackageCreateModal .pkg-create-row Input {
        width: 1fr;
    }
    _PackageCreateModal #pkg-create-mode-bar {
        height: auto;
        padding: 0 0 1 0;
        align: center middle;
    }
    _PackageCreateModal #pkg-create-buttons {
        width: 100%;
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    _PackageCreateModal #pkg-create-error {
        height: auto;
        color: $error;
        padding: 0 0 1 0;
    }
    _PackageCreateModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._mode = "blank"

    def compose(self) -> ComposeResult:
        with Vertical(id="pkg-create-dialog"):
            yield Static("Criar Package", id="pkg-create-title")
            with Horizontal(classes="pkg-create-row"):
                yield Select([], prompt="Selecione a conexao Oracle", id="pkg-create-conn")
            with Horizontal(classes="pkg-create-row"):
                yield Input(placeholder="Nome do package", id="pkg-create-name")
            with Horizontal(id="pkg-create-mode-bar"):
                yield Button(
                    "Em branco", variant="primary", id="pkg-create-mode-blank"
                )
                yield Button(
                    "Wizard", variant="default", id="pkg-create-mode-wizard"
                )
            yield Static("", id="pkg-create-error")
            with Horizontal(id="pkg-create-buttons"):
                yield Button("Criar", variant="primary", id="pkg-create-go")
                yield Button("Cancelar", variant="default", id="pkg-create-cancel")

    def on_mount(self) -> None:
        self._load_oracle_connections()
        self.query_one("#pkg-create-error").display = False

    def _load_oracle_connections(self) -> None:
        from dbqm.models.connection import load_connections

        connections = load_connections()
        oracle_conns = [c for c in connections if c.db_type == "oracle"]
        options = [
            (f"{c.name} ({c.display_target()})", c.name)
            for c in oracle_conns
        ]
        self.query_one("#pkg-create-conn", Select).set_options(options)

        if not oracle_conns:
            self.query_one("#pkg-create-error", Static).update(
                "Nenhuma conexao Oracle configurada."
            )
            self.query_one("#pkg-create-error").display = True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "pkg-create-mode-blank":
            self._mode = "blank"
            self.query_one("#pkg-create-mode-blank", Button).variant = "primary"
            self.query_one("#pkg-create-mode-wizard", Button).variant = "default"
        elif btn_id == "pkg-create-mode-wizard":
            self._mode = "wizard"
            self.query_one("#pkg-create-mode-wizard", Button).variant = "primary"
            self.query_one("#pkg-create-mode-blank", Button).variant = "default"
        elif btn_id == "pkg-create-go":
            self._handle_create()
        elif btn_id == "pkg-create-cancel":
            self.dismiss(None)

    def _handle_create(self) -> None:
        from dbqm.core.package_editor import generate_blank_template

        select = self.query_one("#pkg-create-conn", Select)
        conn_name = select.value
        if conn_name is Select.BLANK:
            self.query_one("#pkg-create-error", Static).update("Selecione uma conexao.")
            self.query_one("#pkg-create-error").display = True
            return

        pkg_name = self.query_one("#pkg-create-name", Input).value.strip()
        if not pkg_name:
            self.query_one("#pkg-create-error", Static).update(
                "Informe o nome do package."
            )
            self.query_one("#pkg-create-error").display = True
            return

        self.query_one("#pkg-create-error").display = False

        if self._mode == "wizard":
            self.app.push_screen(
                _WizardRoutineModal(),
                callback=lambda routines: self._on_wizard_result(
                    conn_name, pkg_name.upper(), routines
                ),
            )
        else:
            spec, body = generate_blank_template(pkg_name)
            self.dismiss({
                "conn_name": conn_name,
                "pkg_name": pkg_name.upper(),
                "spec": spec,
                "body": body,
                "mode": "blank",
            })

    def _on_wizard_result(
        self, conn_name: str, pkg_name: str, routines: list[dict] | None
    ) -> None:
        if routines is None or not routines:
            # User cancelled wizard — fall back to blank
            from dbqm.core.package_editor import generate_blank_template

            spec, body = generate_blank_template(pkg_name)
        else:
            from dbqm.core.package_editor import generate_wizard_template

            spec, body = generate_wizard_template(pkg_name, routines)

        self.dismiss({
            "conn_name": conn_name,
            "pkg_name": pkg_name,
            "spec": spec,
            "body": body,
            "mode": "wizard" if routines else "blank",
        })

    def action_cancel(self) -> None:
        self.dismiss(None)


class _WizardRoutineModal(ModalScreen[list[dict] | None]):
    """Add routines one at a time for the wizard template."""

    DEFAULT_CSS = """
    _WizardRoutineModal {
        align: center middle;
    }
    _WizardRoutineModal #wizard-dialog {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    _WizardRoutineModal #wizard-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    _WizardRoutineModal .wizard-row {
        height: auto;
        padding: 0 0 1 0;
    }
    _WizardRoutineModal .wizard-row Select {
        width: 1fr;
    }
    _WizardRoutineModal .wizard-row Input {
        width: 1fr;
    }
    _WizardRoutineModal #wizard-list {
        height: auto;
        max-height: 10;
        padding: 0 0 1 0;
        color: $text-muted;
    }
    _WizardRoutineModal #wizard-buttons {
        width: 100%;
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    _WizardRoutineModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._routines: list[dict] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="wizard-dialog"):
            yield Static("Wizard - Adicionar Rotinas", id="wizard-title")
            with Horizontal(classes="wizard-row"):
                yield Input(placeholder="Nome da rotina", id="wizard-routine-name")
            with Horizontal(classes="wizard-row"):
                yield Select(
                    [("PROCEDURE", "PROCEDURE"), ("FUNCTION", "FUNCTION")],
                    value="PROCEDURE",
                    id="wizard-routine-type",
                )
            with Horizontal(classes="wizard-row"):
                yield Input(
                    placeholder="Parametros (ex: p_id IN NUMBER, p_name IN VARCHAR2)",
                    id="wizard-routine-params",
                )
            with Horizontal(classes="wizard-row"):
                yield Input(
                    placeholder="Tipo de retorno (apenas para FUNCTION)",
                    id="wizard-routine-return",
                )
            yield Static("Nenhuma rotina adicionada.", id="wizard-list")
            with Horizontal(id="wizard-buttons"):
                yield Button("Adicionar", variant="primary", id="wizard-add")
                yield Button("Concluir", variant="default", id="wizard-done")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "wizard-add":
            self._handle_add()
        elif event.button.id == "wizard-done":
            self.dismiss(self._routines if self._routines else None)

    def _handle_add(self) -> None:
        name = self.query_one("#wizard-routine-name", Input).value.strip()
        if not name:
            return

        rtype_select = self.query_one("#wizard-routine-type", Select)
        rtype = rtype_select.value
        if rtype is Select.BLANK:
            rtype = "PROCEDURE"

        params = self.query_one("#wizard-routine-params", Input).value.strip()
        return_type = self.query_one("#wizard-routine-return", Input).value.strip()

        routine = {
            "name": name.upper(),
            "type": rtype,
            "params": params,
            "return_type": return_type if rtype == "FUNCTION" else None,
        }
        self._routines.append(routine)

        # Update list display
        lines = []
        for r in self._routines:
            sig = f"  {r['type']} {r['name']}"
            if r.get("params"):
                sig += f"({r['params']})"
            if r["type"] == "FUNCTION" and r.get("return_type"):
                sig += f" RETURN {r['return_type']}"
            lines.append(sig)
        self.query_one("#wizard-list", Static).update("\n".join(lines))

        # Clear inputs for next routine
        self.query_one("#wizard-routine-name", Input).value = ""
        self.query_one("#wizard-routine-params", Input).value = ""
        self.query_one("#wizard-routine-return", Input).value = ""
        self.query_one("#wizard-routine-name", Input).focus()

    def action_cancel(self) -> None:
        self.dismiss(None)


# ======================================================================
# Main Screen
# ======================================================================


class PackageEditorScreen(Vertical):
    """Screen widget for editing and compiling Oracle packages.

    Workflow:
    1. Modal to choose edit/new
    2. Modal to search or create the package
    3. Editor with tab bar (Spec/Body), TextArea, and error panel
    """

    DEFAULT_CSS = """
    PackageEditorScreen {
        height: 1fr;
    }
    PackageEditorScreen #pe-info-bar {
        height: auto;
        padding: 0 1;
        background: $surface;
        color: $text-muted;
    }
    PackageEditorScreen #pe-tab-bar {
        height: auto;
        padding: 0 1;
    }
    PackageEditorScreen #pe-tab-bar Button {
        margin: 0 1 0 0;
        min-width: 12;
    }
    PackageEditorScreen #pe-editor-area {
        height: 1fr;
        margin: 0 1;
    }
    PackageEditorScreen #pe-error-panel {
        height: auto;
        max-height: 8;
        padding: 0 1;
        background: $surface;
        overflow-y: auto;
    }
    PackageEditorScreen #pe-empty {
        height: 1fr;
        content-align: center middle;
        text-align: center;
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
        self._spec_content: str = ""
        self._body_content: str = ""
        self._active_tab: str = "spec"
        self._pkg_name: str = ""
        self._conn_name: str = ""
        self._db = None

    def compose(self) -> ComposeResult:
        yield Static("", id="pe-info-bar")
        with Horizontal(id="pe-tab-bar"):
            yield Button("Spec", variant="primary", id="pe-tab-spec")
            yield Button("Body", variant="default", id="pe-tab-body")
        yield TextArea("", language="sql", id="pe-editor-area")
        yield Static("", id="pe-error-panel")
        yield ProgressIndicator()
        yield Static(
            "[dim]Carregando editor de packages...[/dim]",
            id="pe-empty",
        )

    def on_mount(self) -> None:
        # Hide editor widgets until package is loaded
        self.query_one("#pe-info-bar").display = False
        self.query_one("#pe-tab-bar").display = False
        self.query_one("#pe-editor-area").display = False
        self.query_one("#pe-error-panel").display = False

        # Start the modal flow
        self.app.push_screen(
            _PackageChoiceModal(), callback=self._on_choice_result
        )

    def _on_choice_result(self, result: str | None) -> None:
        if result is None:
            self.query_one("#pe-empty", Static).update(
                "[dim]Editor de packages cancelado. Pressione ESC para voltar.[/dim]"
            )
            return

        if result == "edit":
            self.app.push_screen(
                _PackageSearchModal(), callback=self._on_search_result
            )
        elif result == "new":
            self.app.push_screen(
                _PackageCreateModal(), callback=self._on_create_result
            )

    def _on_search_result(self, result: dict | None) -> None:
        if result is None:
            self.query_one("#pe-empty", Static).update(
                "[dim]Busca cancelada. Pressione ESC para voltar.[/dim]"
            )
            return
        self._setup_editor(
            result["conn_name"],
            result["pkg_name"],
            result["spec"],
            result["body"],
        )

    def _on_create_result(self, result: dict | None) -> None:
        if result is None:
            self.query_one("#pe-empty", Static).update(
                "[dim]Criacao cancelada. Pressione ESC para voltar.[/dim]"
            )
            return
        self._setup_editor(
            result["conn_name"],
            result["pkg_name"],
            result["spec"],
            result["body"],
        )

    def _setup_editor(
        self, conn_name: str, pkg_name: str, spec: str, body: str
    ) -> None:
        """Initialize the editor with package content."""
        self._conn_name = conn_name
        self._pkg_name = pkg_name
        self._spec_content = spec
        self._body_content = body
        self._active_tab = "spec"

        # Update info bar
        info = self.query_one("#pe-info-bar", Static)
        info.update(f"[bold]{pkg_name}[/bold]  |  {conn_name}")

        # Show editor widgets, hide empty
        self.query_one("#pe-empty").display = False
        self.query_one("#pe-info-bar").display = True
        self.query_one("#pe-tab-bar").display = True
        self.query_one("#pe-editor-area").display = True
        self.query_one("#pe-error-panel").display = False

        # Load spec content into TextArea
        editor = self.query_one("#pe-editor-area", TextArea)
        editor.load_text(spec)

        # Update tab button styles
        self._update_tab_buttons()

        # Set up action bar
        self._set_editor_actions()

        # Open DB connection in background
        self._open_db_connection(conn_name)

        # Update breadcrumb
        try:
            from dbqm.ui.widgets.breadcrumb import Breadcrumb

            self.app.query_one(Breadcrumb).set_path(
                ["Ferramentas", "Packages", f"{pkg_name} ({conn_name})"]
            )
        except Exception:
            pass

        # Focus the editor
        self.call_after_refresh(lambda: editor.focus())

    def _update_tab_buttons(self) -> None:
        """Update tab button variants to reflect active tab."""
        spec_btn = self.query_one("#pe-tab-spec", Button)
        body_btn = self.query_one("#pe-tab-body", Button)
        if self._active_tab == "spec":
            spec_btn.variant = "primary"
            body_btn.variant = "default"
        else:
            spec_btn.variant = "default"
            body_btn.variant = "primary"

    def _set_editor_actions(self) -> None:
        """Set up the action bar for the editor."""
        actions = [
            Action("Compilar Spec", "C", "pe_compile_spec"),
            Action("Compilar Body", "B", "pe_compile_body"),
            Action("Salvar .sql", "S", "pe_save_sql"),
        ]
        try:
            action_bar = self.app.query_one(ActionBar)
            action_bar.set_actions(actions)
        except Exception:
            pass

    @work(thread=True)
    def _open_db_connection(self, conn_name: str) -> None:
        """Open a database connection in a background thread."""
        from dbqm.models.connection import find_connection
        from dbqm.core.db_manager import get_connection

        try:
            conn = find_connection(conn_name)
            if conn:
                db = get_connection(conn)
                self.app.call_from_thread(self._store_db, db)
        except Exception as e:
            self.app.call_from_thread(
                self._show_db_error,
                f"Erro ao conectar: {e}",
            )

    def _store_db(self, db) -> None:
        """Store the database connection (main thread)."""
        self._db = db

    def _show_db_error(self, msg: str) -> None:
        """Show database connection error."""
        self.notify(msg, severity="error", timeout=8)

    # ------------------------------------------------------------------
    # Tab switching
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id == "pe-tab-spec":
            self._switch_tab("spec")
        elif btn_id == "pe-tab-body":
            self._switch_tab("body")

    def _switch_tab(self, tab: str) -> None:
        """Switch between spec and body tabs."""
        if tab == self._active_tab:
            return

        editor = self.query_one("#pe-editor-area", TextArea)

        # Save current content
        if self._active_tab == "spec":
            self._spec_content = editor.text
        else:
            self._body_content = editor.text

        # Switch tab
        self._active_tab = tab

        # Load new content
        if tab == "spec":
            editor.load_text(self._spec_content)
        else:
            editor.load_text(self._body_content)

        self._update_tab_buttons()

    # ------------------------------------------------------------------
    # Compile
    # ------------------------------------------------------------------

    def _compile(self, target: str) -> None:
        """Compile spec or body."""
        if not self._db:
            self.notify(
                "Conexao de banco nao disponivel. Aguarde ou reabra a tela.",
                severity="error",
            )
            return

        editor = self.query_one("#pe-editor-area", TextArea)

        # Save current editor content
        if self._active_tab == "spec":
            self._spec_content = editor.text
        else:
            self._body_content = editor.text

        # Get the SQL to compile
        if target == "spec":
            sql = self._spec_content
            obj_type = "PACKAGE"
        else:
            sql = self._body_content
            obj_type = "PACKAGE BODY"

        if not sql.strip():
            self.notify(
                f"Conteudo do {target} esta vazio.", severity="warning"
            )
            return

        self.query_one(ProgressIndicator).start(
            f"Compilando {target}..."
        )
        self._run_compile(sql, obj_type, target)

    @work(thread=True)
    def _run_compile(self, sql: str, obj_type: str, target: str) -> None:
        """Run compilation in a background thread."""
        from dbqm.core.package_editor import compile_package, fetch_compilation_errors

        try:
            success, error_msg = compile_package(self._db, sql)
            errors = fetch_compilation_errors(self._db, self._pkg_name, obj_type)
            self.app.call_from_thread(
                self._on_compile_result, target, success, error_msg, errors
            )
        except Exception as e:
            self.app.call_from_thread(self._on_compile_error, str(e))

    def _on_compile_result(
        self,
        target: str,
        success: bool,
        error_msg: str,
        errors: list[dict],
    ) -> None:
        """Handle compilation result on the main thread."""
        self.query_one(ProgressIndicator).stop()
        error_panel = self.query_one("#pe-error-panel", Static)

        if errors:
            # Show compilation errors
            lines = [
                f"[bold $op-falha]  {len(errors)} erro(s) de compilacao ({target.upper()})[/]"
            ]
            for err in errors:
                lines.append(
                    f"  Linha {err['line']}, Col {err['col']}: {err['message']}"
                )
            error_panel.update("\n".join(lines))
            error_panel.display = True
        elif not success:
            error_panel.update(f"[bold $op-falha]Erro: {error_msg}[/]")
            error_panel.display = True
        else:
            error_panel.update(
                f"  {target.capitalize()} compilado com sucesso!"
            )
            error_panel.display = True
            self.notify(
                f"{target.capitalize()} compilado com sucesso!", timeout=5
            )

    def _on_compile_error(self, msg: str) -> None:
        """Handle compilation exception."""
        self.query_one(ProgressIndicator).stop()
        self.notify(f"Erro na compilacao: {msg}", severity="error", timeout=8)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def _save_sql(self) -> None:
        """Export spec + body as a .sql file."""
        from dbqm.core.exporter import export_sql_file

        editor = self.query_one("#pe-editor-area", TextArea)

        # Save current editor content
        if self._active_tab == "spec":
            self._spec_content = editor.text
        else:
            self._body_content = editor.text

        # Combine spec + body
        parts = []
        if self._spec_content.strip():
            parts.append(self._spec_content.strip())
        if self._body_content.strip():
            parts.append(self._body_content.strip())

        if not parts:
            self.notify("Nenhum conteudo para salvar.", severity="warning")
            return

        combined = "\n\n/\n\n".join(parts)

        try:
            label = self._pkg_name or "package"
            path = export_sql_file(combined, label)
            self.notify(f"Exportado: {path}", timeout=5)
        except Exception as e:
            self.notify(f"Erro ao exportar: {e}", severity="error")

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "pe_compile_spec":
            self._compile("spec")
        elif action == "pe_compile_body":
            self._compile("body")
        elif action == "pe_save_sql":
            self._save_sql()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def on_unmount(self) -> None:
        """Close database connection when leaving the screen."""
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

        try:
            self.app.query_one(ActionBar).set_actions([])
        except Exception:
            pass
