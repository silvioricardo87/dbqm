"""Settings screen — theme, audit log, and config portability."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.widgets import Button, Select, Static, Switch


class SettingsScreen(VerticalScroll):
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
    """

    def compose(self) -> ComposeResult:
        # Theme section
        with Vertical(classes="settings-section"):
            yield Static("Tema", classes="settings-label")
            yield Select(
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

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = settings.theme

        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

        self.call_after_refresh(self._set_initial_focus)

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
        if event.switch.id != "settings-audit-switch":
            return

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        settings.audit_log_enabled = event.value
        save_settings(settings)
        status = "ativado" if event.value else "desativado"
        self.notify(f"Log de auditoria {status}!")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-export":
            self._open_portability("export")
        elif event.button.id == "btn-import":
            self._open_portability("import")

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
