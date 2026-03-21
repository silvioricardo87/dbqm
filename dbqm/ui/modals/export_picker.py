"""Modal screen for selecting an export format."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ExportPickerModal(ModalScreen[str | None]):
    """Format selection dialog for exports.

    Dismisses with a format string ("csv", "json", "txt", "png")
    on selection, or None on cancel/ESC.
    """

    DEFAULT_CSS = """
    ExportPickerModal {
        align: center middle;
    }

    ExportPickerModal #dialog {
        width: 40;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ExportPickerModal #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
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
        with Vertical(id="dialog"):
            yield Static("Exportar como", id="title")
            yield Button("CSV", variant="primary", id="fmt-csv")
            yield Button("JSON", variant="primary", id="fmt-json")
            yield Button("TXT", variant="primary", id="fmt-txt")
            if self._include_png:
                yield Button("PNG", variant="primary", id="fmt-png")
            yield Button("Cancelar", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id
        if btn_id and btn_id.startswith("fmt-"):
            fmt = btn_id.removeprefix("fmt-")
            self.dismiss(fmt)
        elif btn_id == "cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
