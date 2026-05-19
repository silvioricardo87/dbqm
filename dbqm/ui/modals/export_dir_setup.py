"""Modal for configuring the default export directory."""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Static


class ExportDirSetupModal(ModalScreen[bool]):
    """Configure where exported files are written.

    Dismisses with True after persisting settings, False on cancel/ESC.

    Two states:
    - Checkbox "Sempre usar o diretorio atual" ON (default): uses CWD; input disabled.
    - Checkbox OFF: input enabled; user must type a path that exists.

    On save: writes default_export_dir (empty when checkbox ON, path otherwise)
    and sets export_dir_prompted = True.
    """

    DEFAULT_CSS = """
    ExportDirSetupModal {
        align: center middle;
    }
    ExportDirSetupModal #dialog {
        width: 70;
        height: auto;
        max-height: 90%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    ExportDirSetupModal #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    ExportDirSetupModal #description {
        width: 100%;
        margin-bottom: 1;
    }
    ExportDirSetupModal Checkbox {
        width: 100%;
        margin-bottom: 1;
    }
    ExportDirSetupModal #path-row {
        height: auto;
        width: 100%;
        margin-bottom: 1;
    }
    ExportDirSetupModal #export-dir-input {
        width: 100%;
    }
    ExportDirSetupModal #error-msg {
        width: 100%;
        color: $error;
        margin-bottom: 1;
        display: none;
    }
    ExportDirSetupModal #error-msg.visible {
        display: block;
    }
    ExportDirSetupModal #buttons {
        width: 100%;
        align: center middle;
        height: auto;
    }
    ExportDirSetupModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        initial_use_cwd: bool = True,
        initial_path: str = "",
    ) -> None:
        super().__init__()
        self._initial_use_cwd = initial_use_cwd
        self._initial_path = initial_path

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static("Configurar local de exportacao", id="title")
            yield Static(
                "Escolha onde os arquivos exportados sao salvos. "
                "Por padrao, eles ficam no diretorio onde voce executa o dbqm.",
                id="description",
                markup=False,
            )
            yield Checkbox(
                "Sempre usar o diretorio atual",
                value=self._initial_use_cwd,
                id="use-cwd-checkbox",
            )
            with Vertical(id="path-row"):
                yield Input(
                    value=self._initial_path,
                    placeholder="Ex: C:\\Users\\you\\exports",
                    id="export-dir-input",
                    disabled=self._initial_use_cwd,
                )
            yield Static("", id="error-msg")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        if self._initial_use_cwd:
            self.query_one("#use-cwd-checkbox", Checkbox).focus()
        else:
            self.query_one("#export-dir-input", Input).focus()

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id != "use-cwd-checkbox":
            return
        path_input = self.query_one("#export-dir-input", Input)
        path_input.disabled = event.value
        self._clear_error()
        if not event.value:
            path_input.focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "export-dir-input":
            self._clear_error()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            self._save()
        elif event.button.id == "cancel":
            self.dismiss(False)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "export-dir-input":
            self._save()

    def action_cancel(self) -> None:
        self.dismiss(False)

    def _save(self) -> None:
        use_cwd = self.query_one("#use-cwd-checkbox", Checkbox).value
        raw_path = self.query_one("#export-dir-input", Input).value.strip()

        if use_cwd:
            new_path = ""
        else:
            if not raw_path:
                self._show_error("Informe um caminho ou marque 'usar o diretorio atual'.")
                return
            path_obj = Path(raw_path).expanduser()
            if not path_obj.exists():
                self._show_error(f"Diretorio nao existe: {path_obj}")
                return
            if not path_obj.is_dir():
                self._show_error(f"O caminho nao e um diretorio: {path_obj}")
                return
            new_path = str(path_obj)

        from dbqm.models.settings import load_settings, save_settings

        settings = load_settings()
        settings.default_export_dir = new_path
        settings.export_dir_prompted = True
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
