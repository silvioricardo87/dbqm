"""Modal screen for single text input dialogs."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from dbqm.ui.widgets.dialog import Dialog


class TextInputModal(ModalScreen[str | None]):
    """A single text input dialog.

    Dismisses with the input value on submit, or None on cancel/ESC.
    """

    DEFAULT_CSS = """
    TextInputModal {
        align: center middle;
    }

    TextInputModal #message {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    TextInputModal Input {
        width: 100%;
    }

    TextInputModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }

    TextInputModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self, title: str, message: str = "", default: str = ""
    ) -> None:
        super().__init__()
        self._title_text = title
        self._message = message
        self._default = default

    def compose(self) -> ComposeResult:
        with Dialog(self._title_text, id="dialog"):
            if self._message:
                yield Static(self._message, id="message")
            yield Input(value=self._default, id="text-input")
            with Horizontal(id="buttons"):
                yield Button("OK", variant="primary", id="submit")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#text-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            value = self.query_one("#text-input", Input).value
            self.dismiss(value)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value)

    def action_cancel(self) -> None:
        self.dismiss(None)
