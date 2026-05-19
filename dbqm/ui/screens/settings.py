"""Settings screen — theme, audit log, exports, and config portability."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Select, Static, Switch

from dbqm.ui.utils import NavSelect, NavVerticalScroll


class SettingsScreen(NavVerticalScroll):
    """Screen widget for application settings.

    Uses VerticalScroll so content is accessible on smaller terminals.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        height: 1fr;
        padding: 1 2;
    }
    SettingsScreen .settings-section {
        height: auto;
        margin-bottom: 1;
        padding: 1;
        background: $surface;
        border: round $accent;
    }
    SettingsScreen .settings-label {
        height: auto;
        margin-bottom: 1;
        text-style: bold;
    }
    SettingsScreen #settings-theme-select {
        width: 40;
    }
    SettingsScreen .audit-row {
        height: auto;
    }
    SettingsScreen .audit-row Static {
        width: auto;
        padding: 0 1 0 0;
    }
    SettingsScreen .port-buttons {
        height: auto;
    }
    SettingsScreen .port-buttons Button {
        margin: 0 1 0 0;
    }
    SettingsScreen .export-subgroup {
        height: auto;
        margin-bottom: 1;
    }
    SettingsScreen .export-subgroup-label {
        height: auto;
        text-style: italic;
        color: $text-muted;
        margin-bottom: 1;
    }
    """

    def compose(self) -> ComposeResult:
        # Theme section
        with Vertical(classes="settings-section"):
            yield Static("Tema", classes="settings-label")
            yield NavSelect(
                [
                    ("GitHub Dark", "github-dark"),
                    ("GitHub Light", "github-light"),
                ],
                id="settings-theme-select",
                allow_blank=False,
            )

        # Audit log section
        with Vertical(classes="settings-section"):
            yield Static("Log de auditoria", classes="settings-label")
            with Vertical(classes="audit-row"):
                yield Switch(id="settings-audit-switch")
                yield Static(
                    "[dim]Registra execucoes de consultas e grupos[/]",
                    id="settings-audit-desc",
                    markup=True,
                )

        # Export directory section
        with Vertical(classes="settings-section"):
            yield Static("Exportacao", classes="settings-label")

            # Group 1: directory path + change button
            with Vertical(classes="export-subgroup"):
                yield Static(
                    "[dim]Local onde os arquivos exportados sao salvos. "
                    "Por padrao, o diretorio atual de execucao.[/]",
                    markup=True,
                )
                yield Static("", id="settings-export-dir-current", markup=True)
                with Horizontal(classes="port-buttons"):
                    yield Button("Alterar diretorio", variant="primary", id="btn-export-dir")

            # Group 2: subdirectory toggle (independent option)
            with Vertical(classes="export-subgroup"):
                yield Static("Estrutura de pastas", classes="export-subgroup-label")
                with Vertical(classes="audit-row"):
                    yield Switch(id="settings-export-subdirs-switch")
                    yield Static(
                        "[dim]Criar subdiretorios por tipo (grupos, DDL, SQL). "
                        "Consultas sempre vao direto no diretorio configurado.[/]",
                        markup=True,
                    )

        # Export/Import section
        with Vertical(classes="settings-section"):
            yield Static("Exportar / Importar configuracoes", classes="settings-label")
            yield Static(
                "[dim]Exporte conexoes, consultas e grupos como bundle .dbqm "
                "ou importe de um arquivo existente[/]",
                markup=True,
            )
            with Horizontal(classes="port-buttons"):
                yield Button("Exportar", variant="primary", id="btn-export")
                yield Button("Importar", variant="warning", id="btn-import")

        # Oracle Instant Client manager
        with Vertical(classes="settings-section"):
            yield Static("Oracle Instant Client", classes="settings-label")
            yield Static(
                "[dim]Baixe, extraia e instale o Oracle Instant Client compativel "
                "com seu sistema operacional[/]",
                markup=True,
            )
            with Horizontal(classes="port-buttons"):
                yield Button("Gerenciar clients", variant="primary", id="btn-oracle-clients")

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = settings.theme

        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

        subdirs_switch = self.query_one("#settings-export-subdirs-switch", Switch)
        subdirs_switch.value = settings.create_export_subdirs

        self._refresh_export_dir_label(settings.default_export_dir)

        self.call_after_refresh(self._set_initial_focus)

    def _refresh_export_dir_label(self, configured: str) -> None:
        label = self.query_one("#settings-export-dir-current", Static)
        if configured:
            label.update(f"[b]Diretorio atual:[/] {configured}")
        else:
            label.update(f"[b]Diretorio atual:[/] [dim](usando o diretorio de execucao: {Path.cwd()})[/]")

    def _set_initial_focus(self) -> None:
        try:
            self.query_one("#settings-theme-select", Select).focus()
        except Exception:
            pass

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "settings-theme-select":
            return
        if event.value is None or event.value is Select.BLANK:
            return

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        new_theme = str(event.value)
        if new_theme == settings.theme:
            return
        settings.theme = new_theme
        save_settings(settings)
        try:
            self.app.theme = settings.theme
        except Exception:
            pass
        self.notify(f"Tema alterado: {settings.theme}")

    def on_switch_changed(self, event: Switch.Changed) -> None:
        from dbqm.models.settings import load_settings, save_settings

        if event.switch.id == "settings-audit-switch":
            settings = load_settings()
            settings.audit_log_enabled = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Log de auditoria {status}!")
        elif event.switch.id == "settings-export-subdirs-switch":
            settings = load_settings()
            settings.create_export_subdirs = event.value
            save_settings(settings)
            status = "ativado" if event.value else "desativado"
            self.notify(f"Subdiretorios por tipo: {status}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-export":
            self._open_portability("export")
        elif event.button.id == "btn-import":
            self._open_portability("import")
        elif event.button.id == "btn-oracle-clients":
            self._open_oracle_clients()
        elif event.button.id == "btn-export-dir":
            self._open_export_dir_modal()

    def _open_export_dir_modal(self) -> None:
        """Open the export dir setup modal in edit mode."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

        settings = load_settings()
        modal = ExportDirSetupModal(
            initial_use_cwd=not settings.default_export_dir,
            initial_path=settings.default_export_dir,
        )
        self.app.push_screen(modal, callback=self._on_export_dir_saved)

    def _on_export_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        from dbqm.models.settings import load_settings

        settings = load_settings()
        self._refresh_export_dir_label(settings.default_export_dir)
        self.notify("Diretorio de exportacao atualizado!")

    def _open_portability(self, mode: str) -> None:
        """Load ConfigPortScreen directly in the chosen mode (skip mode selection)."""
        from dbqm.ui.screens.config_port import ConfigPortScreen
        try:
            from textual.containers import Container
            from dbqm.ui.widgets.breadcrumb import Breadcrumb

            screen_area = self.app.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.app.query_one(Breadcrumb).set_path(["Sistema", "Config", "Exportar/Importar"])

            port_screen = ConfigPortScreen(initial_mode=mode, id="config-port-screen")
            screen_area.mount(port_screen)
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")

    def _open_oracle_clients(self) -> None:
        """Open the Oracle Instant Client manager screen."""
        from dbqm.ui.screens.oracle_clients import OracleClientsScreen
        try:
            from textual.containers import Container
            from dbqm.ui.widgets.breadcrumb import Breadcrumb

            screen_area = self.app.query_one("#screen-area", Container)
            screen_area.remove_children()
            self.app.query_one(Breadcrumb).set_path(["Sistema", "Config", "Oracle Clients"])
            screen_area.mount(OracleClientsScreen(id="oracle-clients-screen"))
        except Exception as e:
            self.notify(f"Erro: {e}", severity="error")
