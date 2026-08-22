"""Settings screen — theme, audit log, exports, and config portability."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Button, Select, Static, Switch

from dbqm.ui.theme import get_theme
from dbqm.ui.utils import NavSelect
from dbqm.ui.widgets.panel import Panel


class SettingsScreen(Vertical):
    """Screen widget for application settings.

    Laid out as two columns of Panels: application config on the left,
    Fernet key status and config portability stacked on the right.
    """

    DEFAULT_CSS = """
    SettingsScreen {
        height: 1fr;
        padding: 1 2;
    }
    SettingsScreen #settings-columns {
        height: 1fr;
    }
    SettingsScreen #settings-columns > Panel {
        width: 1fr;
    }
    SettingsScreen #settings-right-column {
        width: 1fr;
        height: 1fr;
    }
    SettingsScreen #settings-right-column > Panel {
        height: 1fr;
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

    ORACLE_CLIENT_ORIGINS = {
        "config": "configuracao do dbqm",
        "clients": "clients instalados pelo dbqm",
        "package": "pasta clients/ do pacote",
        "ORACLE_HOME": "variavel de ambiente ORACLE_HOME",
        "scan": "deteccao automatica no sistema",
    }

    def compose(self) -> ComposeResult:
        with Horizontal(id="settings-columns"):
            with Panel("⚙️  CONFIG DA APLICACAO", id="settings-panel-config"):
                # Theme
                yield Static("Tema", classes="settings-label")
                yield NavSelect(
                    [
                        ("Plano Escuro", "plano-escuro"),
                        ("Plano Claro", "plano-claro"),
                    ],
                    id="settings-theme-select",
                    allow_blank=False,
                )

                # Audit log
                yield Static("Log de auditoria", classes="settings-label")
                with Vertical(classes="audit-row"):
                    yield Switch(id="settings-audit-switch")
                    yield Static(
                        "[dim]Registra execucoes de consultas e grupos[/]",
                        id="settings-audit-desc",
                        markup=True,
                    )

                # Export directory
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

                # Oracle Instant Client manager
                yield Static("Oracle Instant Client", classes="settings-label")
                yield Static(
                    "[dim]Diretorio do client carregado pelo dbqm. Definir aqui tem "
                    "prioridade sobre a variavel ORACLE_HOME do sistema, que outras "
                    "ferramentas podem apontar para um client de outra arquitetura.[/]",
                    markup=True,
                )
                yield Static("", id="settings-oracle-client-current", markup=True)
                with Horizontal(classes="port-buttons"):
                    yield Button("Definir caminho", variant="primary", id="btn-oracle-client-dir")
                    yield Button("Gerenciar clients", variant="default", id="btn-oracle-clients")

            with Vertical(id="settings-right-column"):
                with Panel("🔑  FERNET KEY", id="settings-panel-fernet"):
                    yield Static("", id="settings-fernet-status", markup=True)

                with Panel("📦  PORTABILIDADE", id="settings-panel-portability"):
                    yield Static(
                        "[dim]Exporte conexoes, consultas e grupos como bundle .dbqm "
                        "ou importe de um arquivo existente[/]",
                        markup=True,
                    )
                    with Horizontal(classes="port-buttons"):
                        yield Button("Exportar", variant="primary", id="btn-export")
                        yield Button("Importar", variant="warning", id="btn-import")

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = get_theme(settings.theme).name

        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

        subdirs_switch = self.query_one("#settings-export-subdirs-switch", Switch)
        subdirs_switch.value = settings.create_export_subdirs

        self._refresh_export_dir_label(settings.default_export_dir)
        self._refresh_oracle_client_status()
        self._refresh_fernet_status()

        self.call_after_refresh(self._set_initial_focus)

    def _refresh_export_dir_label(self, configured: str) -> None:
        label = self.query_one("#settings-export-dir-current", Static)
        if configured:
            label.update(f"[b]Diretorio atual:[/] {configured}")
        else:
            label.update(f"[b]Diretorio atual:[/] [dim](usando o diretorio de execucao: {Path.cwd()})[/]")

    def _refresh_oracle_client_status(self) -> None:
        """Show which Instant Client is active and where the choice came from.

        A configured-but-unusable path is reported as an error instead of
        silently falling back — that silence is what made the ORACLE_HOME
        conflict so hard to diagnose.
        """
        from dbqm.core.db_manager import OracleClientConfigError, resolve_oracle_client_dir

        label = self.query_one("#settings-oracle-client-current", Static)
        try:
            path, origin = resolve_oracle_client_dir()
        except OracleClientConfigError as e:
            label.update(f"[b]Client em uso:[/] [$op-falha]{e}[/]")
            return
        if not path:
            label.update(
                "[b]Client em uso:[/] [$texto-apoio]nenhum encontrado[/] "
                "[dim](thick mode indisponivel)[/]"
            )
            return
        source = self.ORACLE_CLIENT_ORIGINS.get(origin, origin)
        label.update(f"[b]Client em uso:[/] {path}\n[b]Origem:[/] {source}")

    def _refresh_fernet_status(self) -> None:
        from dbqm.core.paths import KEY_FILE

        status = self.query_one("#settings-fernet-status", Static)
        exists = KEY_FILE.exists()
        state = "Presente" if exists else "[$texto-apoio]Sera gerada no primeiro uso[/]"
        status.update(
            f"[b]Status:[/b] {state}\n"
            f"[b]Local:[/b] [dim]{KEY_FILE}[/]\n\n"
            "[dim]Chave usada para criptografar senhas de conexao salvas. "
            "Nao ha acao manual necessaria — ela e criada automaticamente.[/]"
        )

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
        elif event.button.id == "btn-oracle-client-dir":
            self._open_oracle_client_dir_modal()
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

    def _open_oracle_client_dir_modal(self) -> None:
        """Open the Instant Client directory modal seeded with the current setting."""
        from dbqm.models.settings import load_settings
        from dbqm.ui.modals.oracle_client_dir import OracleClientDirModal

        modal = OracleClientDirModal(initial_path=load_settings().oracle_client_dir)
        self.app.push_screen(modal, callback=self._on_oracle_client_dir_saved)

    def _on_oracle_client_dir_saved(self, saved: bool | None) -> None:
        if not saved:
            return
        self._refresh_oracle_client_status()
        self.notify("Oracle Instant Client atualizado! Reabra o dbqm para aplicar.")

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
