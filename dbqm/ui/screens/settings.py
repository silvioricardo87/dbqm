"""Settings screen — theme and audit log configuration."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Select, Static, Switch


class SettingsScreen(Vertical):
    """Screen widget for application settings.

    Provides:
    - Theme selector (GitHub Dark / GitHub Light)
    - Audit log toggle
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
        layout: horizontal;
    }
    SettingsScreen .audit-row Static {
        width: auto;
        padding: 0 1 0 0;
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

    def on_mount(self) -> None:
        from dbqm.models.settings import load_settings

        settings = load_settings()

        # Set theme selector value
        theme_select = self.query_one("#settings-theme-select", Select)
        theme_select.value = settings.theme

        # Set audit switch value
        audit_switch = self.query_one("#settings-audit-switch", Switch)
        audit_switch.value = settings.audit_log_enabled

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
