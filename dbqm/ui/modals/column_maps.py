"""Modal for configuring DE-PARA (value mapping) on query columns."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, Select, Static


class ColumnMapsModal(ModalScreen[dict | None]):
    """Configure column value mappings (DE-PARA).

    Dismisses with updated maps dict on save, or None on cancel/ESC.
    """

    DEFAULT_CSS = """
    ColumnMapsModal {
        align: center middle;
    }

    ColumnMapsModal #dialog {
        width: 80;
        max-height: 85%;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }

    ColumnMapsModal #title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }

    ColumnMapsModal #col-select {
        width: 100%;
        margin-bottom: 1;
    }

    ColumnMapsModal #maps-table {
        height: 10;
        margin-bottom: 1;
    }

    ColumnMapsModal .map-input {
        width: 1fr;
    }

    ColumnMapsModal #add-row {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    ColumnMapsModal #buttons {
        margin-top: 1;
        width: 100%;
        align: center middle;
    }

    ColumnMapsModal Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancelar", show=False),
    ]

    def __init__(
        self,
        columns: list[str],
        current_maps: dict[str, dict[str, str]],
    ) -> None:
        super().__init__()
        self._columns = columns
        # Deep copy so we don't mutate the original
        self._maps: dict[str, dict[str, str]] = {
            col: dict(mappings) for col, mappings in current_maps.items()
        }
        self._selected_col: str = ""

    def compose(self) -> ComposeResult:
        options = [(col, col) for col in self._columns]
        with Vertical(id="dialog"):
            yield Static("DE-PARA (Mapeamento de Valores)", id="title")
            yield Select(options, prompt="Selecione uma coluna", id="col-select")
            yield DataTable(id="maps-table")
            with Horizontal(id="add-row"):
                yield Input(placeholder="Valor original", id="raw-input", classes="map-input")
                yield Input(placeholder="Exibir como", id="display-input", classes="map-input")
                yield Button("+", variant="success", id="add-map")
            yield Button("Remover selecionado", variant="error", id="remove-map")
            with Horizontal(id="buttons"):
                yield Button("Salvar", variant="primary", id="save")
                yield Button("Cancelar", variant="default", id="cancel")

    def on_mount(self) -> None:
        table = self.query_one("#maps-table", DataTable)
        table.cursor_type = "row"
        table.add_columns("Valor Original", "Exibir Como")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.value is not Select.BLANK:
            self._selected_col = str(event.value)
            self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#maps-table", DataTable)
        table.clear()
        mappings = self._maps.get(self._selected_col, {})
        for raw, display in mappings.items():
            table.add_row(raw, display)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "add-map":
            self._add_mapping()
        elif event.button.id == "remove-map":
            self._remove_mapping()
        elif event.button.id == "save":
            # Clean up empty column maps
            clean = {col: m for col, m in self._maps.items() if m}
            self.dismiss(clean)
        elif event.button.id == "cancel":
            self.dismiss(None)

    def _add_mapping(self) -> None:
        if not self._selected_col:
            self.notify("Selecione uma coluna primeiro.", severity="warning")
            return
        raw_input = self.query_one("#raw-input", Input)
        display_input = self.query_one("#display-input", Input)
        raw = raw_input.value.strip()
        display = display_input.value.strip()
        if not raw or not display:
            self.notify("Preencha ambos os campos.", severity="warning")
            return
        if self._selected_col not in self._maps:
            self._maps[self._selected_col] = {}
        self._maps[self._selected_col][raw] = display
        raw_input.value = ""
        display_input.value = ""
        self._refresh_table()

    def _remove_mapping(self) -> None:
        if not self._selected_col:
            return
        table = self.query_one("#maps-table", DataTable)
        if table.row_count == 0:
            return
        try:
            row_key = table.cursor_row
            row = table.get_row_at(row_key)
            raw_val = str(row[0])
            mappings = self._maps.get(self._selected_col, {})
            mappings.pop(raw_val, None)
            self._refresh_table()
        except Exception:
            pass

    def action_cancel(self) -> None:
        self.dismiss(None)
