"""Modal screen for entering query parameters before execution."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Static

from dbqm.ui.utils import sanitize_id


class ParamModal(ModalScreen[dict[str, str] | None]):
    """Modal for collecting query parameter values.

    Displays one Input per parameter, pre-filled with defaults or last-used
    values. Dismisses with a dict of param values on submit, or None on cancel.
    """

    DEFAULT_CSS = """
    ParamModal {
        align: center middle;
    }

    ParamModal #dialog {
        width: 70;
        max-height: 80%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
        overflow-y: auto;
    }

    ParamModal #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    ParamModal #subtitle {
        width: 100%;
        content-align: center middle;
        color: $text-muted;
        margin-bottom: 1;
    }

    ParamModal .param-label {
        margin-top: 1;
    }

    ParamModal Input {
        width: 100%;
    }

    ParamModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }

    ParamModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        query_name: str,
        params: list[dict],
        last_values: dict[str, str] | None = None,
        description: str = "",
    ) -> None:
        super().__init__()
        self.query_name = query_name
        self.params = params
        self.last_values = last_values or {}
        self.description = description
        self._param_id_to_name: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dialog"):
            yield Static(self.query_name, id="title")
            if self.description:
                yield Static(self.description, id="subtitle")

            for param in self.params:
                name = param["name"]
                desc = param.get("description", "")
                default = param.get("default", "")

                label_text = f":{name}"
                if desc:
                    label_text += f" ({desc})"

                yield Label(label_text, classes="param-label")

                value = self.last_values.get(name, default)
                safe_id = sanitize_id(name)
                self._param_id_to_name[safe_id] = name
                yield Input(
                    value=value,
                    placeholder=default if not value else "",
                    id=f"param-{safe_id}",
                )

            with Horizontal(id="buttons"):
                yield Button("Executar", variant="primary", id="submit")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        """Focus the first empty input, or the first input if all are filled."""
        inputs = self.query(Input)
        for inp in inputs:
            if not inp.value:
                inp.focus()
                return
        if inputs:
            inputs.first().focus()

    def _collect_values(self) -> dict[str, str]:
        """Collect all input values into a dict keyed by param name."""
        values: dict[str, str] = {}
        for param in self.params:
            name = param["name"]
            safe_id = sanitize_id(name)
            inp = self.query_one(f"#param-{safe_id}", Input)
            values[name] = inp.value
        return values

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.dismiss(self._collect_values())
        elif event.button.id == "cancel":
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """When Enter is pressed on an input, move to next or submit."""
        inputs = list(self.query(Input))
        try:
            idx = inputs.index(event.input)
        except ValueError:
            return

        if idx < len(inputs) - 1:
            inputs[idx + 1].focus()
        else:
            self.dismiss(self._collect_values())

    def action_cancel(self) -> None:
        self.dismiss(None)
