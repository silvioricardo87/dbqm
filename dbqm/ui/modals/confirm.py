"""Modal screen for yes/no confirmation dialogs."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from dbqm.ui.widgets.dialog import Dialog


class ConfirmModal(ModalScreen[bool]):
    """A simple yes/no confirmation dialog.

    Dismisses with True on confirm, False on cancel or ESC.
    """

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal #message {
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    ConfirmModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }

    ConfirmModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, message: str, title: str = "Confirmar") -> None:
        super().__init__()
        self._title_text = title
        self._message = message

    def compose(self) -> ComposeResult:
        with Dialog(self._title_text, id="dialog"):
            yield Static(self._message, id="message")
            with Horizontal(id="buttons"):
                yield Button("Sim", variant="primary", id="confirm")
                yield Button("Nao", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm":
            self.dismiss(True)
        elif event.button.id == "cancel":
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)
