"""Config portability screen — export/import configurations."""
from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Checkbox, Input, Static

from dbqm.ui.widgets.panel import Panel


class ConfigPortScreen(Vertical):
    """Screen widget for exporting and importing configurations.

    Export flow: select items, enter password, create .dbqm bundle.
    Import flow: enter file path, enter password, import.

    Pass initial_mode="export" or "import" to skip mode selection.
    """

    DEFAULT_CSS = """
    ConfigPortScreen {
        height: 1fr;
        padding: 1 2;
        /* O formulario de importacao passa da dobra num terminal de 24
           linhas assim que os dois campos e a barra de acoes se somam a
           moldura: a tela rola, em vez de esconder o botao Importar. */
        overflow-y: auto;
    }
    ConfigPortScreen Panel {
        height: auto;
    }
    ConfigPortScreen .cp-mode-buttons {
        height: auto;
        margin-top: 1;
    }
    ConfigPortScreen .cp-mode-buttons Button {
        margin-right: 1;
        min-width: 20;
    }

    /* -- Export phase -- */
    ConfigPortScreen .cp-checks {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-checks Checkbox {
        margin-bottom: 0;
        height: auto;
    }
    ConfigPortScreen .cp-password-row {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-password-row Input {
        width: 40;
    }
    ConfigPortScreen .cp-password-row Static {
        width: auto;
        padding: 0 0 0 0;
    }

    /* -- Import phase -- */
    ConfigPortScreen .cp-field {
        height: auto;
        margin-bottom: 1;
    }
    ConfigPortScreen .cp-field-label {
        height: auto;
        text-style: bold;
    }
    ConfigPortScreen .cp-field Input {
        width: 60;
    }

    /* -- Actions -- */
    ConfigPortScreen .cp-actions {
        height: auto;
        margin-top: 1;
    }
    ConfigPortScreen .cp-actions Button {
        margin-right: 1;
    }
    """

    def __init__(self, initial_mode: str | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self._initial_mode = initial_mode

    def compose(self) -> ComposeResult:
        # Phase 1: mode selection
        with Panel("🔄  EXPORTAR OU IMPORTAR", id="cp-mode-phase"):
            with Horizontal(classes="cp-mode-buttons"):
                yield Button("Exportar", id="cp-btn-export", variant="primary")
                yield Button("Importar", id="cp-btn-import", variant="default")

        # Phase 2: export form
        with Panel("⬆️  EXPORTAR CONFIGURACOES", id="cp-export-phase"):
            with Vertical(classes="cp-checks"):
                yield Checkbox("Conexoes", id="cp-chk-connections", value=True)
                yield Checkbox("Consultas", id="cp-chk-queries", value=True)
                yield Checkbox("Grupos", id="cp-chk-groups", value=True)
            with Vertical(classes="cp-password-row"):
                yield Static("Senha:", classes="cp-field-label")
                yield Input(placeholder="Senha para proteger o arquivo", password=True, id="cp-export-password")
            with Vertical(classes="cp-password-row"):
                yield Static("Confirmar senha:", classes="cp-field-label")
                yield Input(placeholder="Confirme a senha", password=True, id="cp-export-password-confirm")
            with Horizontal(classes="cp-actions"):
                yield Button("Exportar", id="cp-do-export", variant="primary")
                yield Button("Voltar", id="cp-export-back", variant="default")

        # Phase 3: import form
        with Panel("⬇️  IMPORTAR CONFIGURACOES", id="cp-import-phase"):
            with Vertical(classes="cp-field"):
                yield Static("Caminho do arquivo .dbqm:", classes="cp-field-label")
                yield Input(placeholder="Ex: C:\\exports\\config.dbqm", id="cp-import-path")
            with Vertical(classes="cp-field"):
                yield Static("Senha do arquivo:", classes="cp-field-label")
                yield Input(placeholder="Senha usada na exportacao", password=True, id="cp-import-password")
            with Horizontal(classes="cp-actions"):
                yield Button("Importar", id="cp-do-import", variant="primary")
                yield Button("Voltar", id="cp-import-back", variant="default")

    def on_mount(self) -> None:
        if self._initial_mode == "export":
            self._show_export_phase()
        elif self._initial_mode == "import":
            self._show_import_phase()
        else:
            self._show_mode_phase()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        try:
            if self._initial_mode == "export":
                self.query_one("#cp-chk-connections", Checkbox).focus()
            elif self._initial_mode == "import":
                self.query_one("#cp-import-path", Input).focus()
            else:
                self.query_one("#cp-btn-export", Button).focus()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Phase management
    # ------------------------------------------------------------------

    def _show_mode_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = True
        self.query_one("#cp-export-phase").display = False
        self.query_one("#cp-import-phase").display = False

    def _show_export_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = False
        self.query_one("#cp-export-phase").display = True
        self.query_one("#cp-import-phase").display = False

    def _show_import_phase(self) -> None:
        self.query_one("#cp-mode-phase").display = False
        self.query_one("#cp-export-phase").display = False
        self.query_one("#cp-import-phase").display = True

    def _go_back_to_settings(self) -> None:
        """Navigate back to the Settings screen."""
        try:
            from dbqm.ui.screens.settings import SettingsScreen
            from textual.containers import Container
            from dbqm.ui.widgets.breadcrumb import Breadcrumb

            screen_area = self.app.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.app.query_one(Breadcrumb).set_path(["Sistema", "Config"])

            settings = SettingsScreen(id="settings-screen")
            screen_area.mount(settings)
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id == "cp-btn-export":
            self._show_export_phase()
        elif btn_id == "cp-btn-import":
            self._show_import_phase()
        elif btn_id in ("cp-export-back", "cp-import-back"):
            if self._initial_mode:
                self._go_back_to_settings()
            else:
                self._show_mode_phase()
        elif btn_id == "cp-do-export":
            self._handle_export()
        elif btn_id == "cp-do-import":
            self._handle_import()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _handle_export(self) -> None:
        password = self.query_one("#cp-export-password", Input).value.strip()
        password_confirm = self.query_one("#cp-export-password-confirm", Input).value.strip()

        if not password:
            self.notify("Senha obrigatoria para exportar.", severity="warning")
            return

        if password != password_confirm:
            self.notify("Senhas nao conferem.", severity="error")
            return

        include_connections = self.query_one("#cp-chk-connections", Checkbox).value
        include_queries = self.query_one("#cp-chk-queries", Checkbox).value
        include_groups = self.query_one("#cp-chk-groups", Checkbox).value

        if not (include_connections or include_queries or include_groups):
            self.notify("Selecione ao menos um item para exportar.", severity="warning")
            return

        self._run_export(password, include_connections, include_queries, include_groups)

    @work(thread=True)
    def _run_export(
        self,
        password: str,
        include_connections: bool,
        include_queries: bool,
        include_groups: bool,
    ) -> None:
        from dbqm.core.config_portability import export_configs

        try:
            path = export_configs(
                password=password,
                include_connections=include_connections,
                include_queries=include_queries,
                include_groups=include_groups,
            )
            self.app.call_from_thread(
                self.notify, f"Configuracoes exportadas: {path}", severity="information", timeout=8
            )
            self.app.call_from_thread(self._clear_export_form)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Erro ao exportar: {e}", severity="error", timeout=8
            )

    def _clear_export_form(self) -> None:
        self.query_one("#cp-export-password", Input).value = ""
        self.query_one("#cp-export-password-confirm", Input).value = ""

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    def _handle_import(self) -> None:
        filepath = self.query_one("#cp-import-path", Input).value.strip().strip('"').strip("'")
        password = self.query_one("#cp-import-password", Input).value.strip()

        if not filepath:
            self.notify("Informe o caminho do arquivo .dbqm.", severity="warning")
            return

        if not Path(filepath).exists():
            self.notify("Arquivo nao encontrado.", severity="error")
            return

        if not password:
            self.notify("Informe a senha do arquivo.", severity="warning")
            return

        self._run_import(filepath, password)

    @work(thread=True)
    def _run_import(self, filepath: str, password: str) -> None:
        from dbqm.core.config_portability import import_configs

        try:
            summary = import_configs(filepath, password)
            total = summary["connections"] + summary["queries"] + summary["groups"]
            parts = []
            if summary["connections"]:
                parts.append(f'{summary["connections"]} conexoes')
            if summary["queries"]:
                parts.append(f'{summary["queries"]} consultas')
            if summary["groups"]:
                parts.append(f'{summary["groups"]} grupos')
            if summary["skipped"]:
                parts.append(f'{summary["skipped"]} ignorados (duplicados)')

            if total > 0:
                msg = f"Importado: {', '.join(parts)}"
                self.app.call_from_thread(self.notify, msg, severity="information", timeout=8)
            else:
                msg = f"Nenhuma configuracao nova importada. {summary['skipped']} duplicados ignorados."
                self.app.call_from_thread(self.notify, msg, severity="warning", timeout=8)

            self.app.call_from_thread(self._clear_import_form)
            self.app.call_from_thread(self._update_status_bar)
        except Exception as e:
            self.app.call_from_thread(
                self.notify, f"Erro ao importar: {e}", severity="error", timeout=8
            )

    def _clear_import_form(self) -> None:
        self.query_one("#cp-import-path", Input).value = ""
        self.query_one("#cp-import-password", Input).value = ""

    def _update_status_bar(self) -> None:
        try:
            from dbqm.models.connection import load_connections
            from dbqm.models.query import load_queries
            from dbqm.models.group import load_groups
            from dbqm.ui.widgets.status_bar import StatusBar

            status_bar = self.app.query_one(StatusBar)
            status_bar.update_counts(
                connections=len(load_connections()),
                queries=len(load_queries()),
                groups=len(load_groups()),
            )
        except Exception:
            pass
