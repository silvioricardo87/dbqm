"""Modal for configuring the Oracle Instant Client directory."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Static

from dbqm.ui.widgets.dialog import Dialog


class OracleClientDirModal(ModalScreen[bool]):
    """Choose which Oracle Instant Client dbqm loads.

    Dismisses with True after persisting settings, False on cancel/ESC.

    Two states:
    - Checkbox "Detectar automaticamente" ON: clears the setting; dbqm falls
      back to ~/.dbqm/clients/ and, as a last resort, ORACLE_HOME.
    - Checkbox OFF: the typed path is validated (it must exist and, on Windows,
      match the running Python's architecture) before being saved.

    The setting only takes effect on the next dbqm start: python-oracledb can
    initialize the client library once per process.
    """

    DEFAULT_CSS = """
    OracleClientDirModal {
        align: center middle;
    }
    OracleClientDirModal #description {
        width: 100%;
        margin-bottom: 1;
    }
    OracleClientDirModal Checkbox {
        width: 100%;
        margin-bottom: 1;
    }
    OracleClientDirModal #path-row {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }
    OracleClientDirModal #oracle-client-dir-input {
        width: 100%;
    }
    OracleClientDirModal #restart-note {
        width: 100%;
        color: $text-muted;
        margin-bottom: 1;
    }
    OracleClientDirModal #error-msg {
        width: 100%;
        color: $error;
        margin-bottom: 1;
        display: none;
    }
    OracleClientDirModal #error-msg.visible {
        display: block;
    }
    OracleClientDirModal #buttons {
        width: 100%;
        align: center middle;
        height: auto;
    }
    OracleClientDirModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(self, initial_path: str = "") -> None:
        super().__init__()
        self._initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Dialog("Oracle Instant Client", width="lg", id="dialog"):
            yield Static(
                "Informe o diretorio do Instant Client que o dbqm deve carregar. "
                "Definir aqui evita conflito com a variavel ORACLE_HOME do sistema, "
                "que outras ferramentas (como o PL/SQL Developer) podem apontar "
                "para um client de arquitetura diferente.",
                id="description",
                markup=False,
            )
            yield Checkbox(
                "Detectar automaticamente",
                value=not self._initial_path,
                id="use-auto-checkbox",
            )
            with Vertical(id="path-row"):
                yield Input(
                    value=self._initial_path,
                    placeholder="Ex: C:\\Users\\you\\.dbqm\\clients\\instantclient_19_x64",
                    id="oracle-client-dir-input",
                    disabled=not self._initial_path,
                )
            yield Static(
                "A troca passa a valer na proxima vez que o dbqm for aberto.",
                id="restart-note",
                markup=False,
            )
            yield Static("", id="error-msg")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        if self._initial_path:
            self.query_one("#oracle-client-dir-input", Input).focus()
        else:
            self.query_one("#use-auto-checkbox", Checkbox).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "use-auto-checkbox":
            return
        path_input = self.query_one("#oracle-client-dir-input", Input)
        path_input.disabled = event.value
        self._clear_error()
        if not event.value:
            path_input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "oracle-client-dir-input":
            self._clear_error()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "oracle-client-dir-input":
            self._save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(False)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _save(self) -> None:
        from dbqm.core.db_manager import validate_oracle_client_dir

        use_auto = self.query_one("#use-auto-checkbox", Checkbox).value
        raw_path = self.query_one("#oracle-client-dir-input", Input).value.strip()

        if use_auto:
            new_path = ""
        else:
            if not raw_path:
                self._show_error("Informe um caminho ou marque 'Detectar automaticamente'.")
                return
            problem = validate_oracle_client_dir(raw_path)
            if problem:
                self._show_error(problem)
                return
            new_path = str(Path(raw_path).expanduser())

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        settings.oracle_client_dir = new_path
        save_settings(settings)
        self.dismiss(True)

    def _show_error(self, message: str) -> None:
        err = self.query_one("#error-msg", Static)
        err.update(message)
        err.add_class("visible")

    def _clear_error(self) -> None:
        err = self.query_one("#error-msg", Static)
        err.update("")
        err.remove_class("visible")
