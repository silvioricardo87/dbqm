"""Error display modal — shows error details instead of crashing the app."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from dbqm.ui.widgets.dialog import Dialog


class ErrorModal(ModalScreen[None]):
    """Displays an error message with details in a modal overlay."""

    DEFAULT_CSS = """
    ErrorModal {
        align: center middle;
    }
    ErrorModal #error-scroll {
        height: 1fr;
        margin-bottom: 1;
    }
    ErrorModal #error-detail {
        width: 100%;
    }
    ErrorModal Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "close", "Fechar", show=False),
        Binding("enter", "close", "Fechar", show=False),
    ]

    def __init__(self, title: str, detail: str) -> None:
        super().__init__()
        self._title = title
        self._detail = detail

    def compose(self) -> ComposeResult:
        with Dialog(self._title, id="error-dialog", tom="destrutivo", largura="lg"):
            with VerticalScroll(id="error-scroll"):
                yield Static(self._detail, id="error-detail")
            yield Button("Fechar", variant="error", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_close(self) -> None:
        self.dismiss(None)
