"""Modal screen for selecting an export format."""
from __future__ import annotations

from typing import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Button

from dbqm.ui.widgets.dialog import Dialog


class ExportPickerModal(ModalScreen[str | None]):
    """Format selection dialog for exports.

    Dismisses with a format string ("csv", "json", "txt", "png")
    on selection, or None on cancel/ESC.
    """

    DEFAULT_CSS = """
    ExportPickerModal {
        align: center middle;
    }

    ExportPickerModal Button {
        width: 100%;
        margin: 0 0 1 0;
    }

    ExportPickerModal #cancel {
        margin-top: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, include_png: bool = False) -> None:
        super().__init__()
        self._include_png = include_png

    def compose(self) -> ComposeResult:
        with Dialog("Exportar como", width="sm", id="dialog"):
            yield Button("CSV", variant="primary", id="fmt-csv")
            yield Button("JSON", variant="primary", id="fmt-json")
            yield Button("TXT", variant="primary", id="fmt-txt")
            if self._include_png:
                yield Button("PNG", variant="primary", id="fmt-png")
            yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Focus the first format button."""
        self.query_one("#fmt-csv", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id and btn_id.startswith("fmt-"):
            fmt = btn_id.removeprefix("fmt-")
            self.dismiss(fmt)
        elif btn_id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


def request_export(
    app,
    include_png: bool = False,
    callback: Callable[[str | None], None] | None = None,
) -> None:
    """Public entry point for the export flow.

    On the first export ever, prompts the user to choose an export directory
    (via ExportDirSetupModal) and only then shows the format picker. If the
    user cancels the setup modal, the export is aborted — settings are left
    untouched so the prompt fires again next time.

    After the first successful setup (or whenever the setting has already been
    persisted), goes directly to the format picker.
    """
    from dbqm.models.settings import load_settings
    from dbqm.ui.modals.export_dir_setup import ExportDirSetupModal

    def _show_picker() -> None:
        app.push_screen(ExportPickerModal(include_png=include_png), callback=callback)

    settings = load_settings()
    if settings.export_dir_prompted:
        _show_picker()
        return

    def _after_setup(saved: bool | None) -> None:
        if saved:
            _show_picker()
        elif callback is not None:
            callback(None)

    app.push_screen(
        ExportDirSetupModal(
            initial_use_cwd=not settings.default_export_dir,
            initial_path=settings.default_export_dir,
        ),
        callback=_after_setup,
    )
