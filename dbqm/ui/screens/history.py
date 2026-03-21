"""History screen — browse execution history."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Static

from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected


class HistoryScreen(Vertical):
    """Screen widget for browsing execution history.

    Shows a DataTable with the last 50 history entries and
    allows viewing details or clearing history.
    """

    DEFAULT_CSS = """
    HistoryScreen {
        height: 1fr;
    }
    HistoryScreen #hist-list-phase {
        height: 1fr;
        padding: 1;
    }
    HistoryScreen #hist-empty {
        height: auto;
        padding: 2;
        content-align: center middle;
        text-align: center;
        color: $text-muted;
    }
    HistoryScreen #hist-table {
        height: 1fr;
    }
    HistoryScreen #hist-detail-phase {
        height: 1fr;
        padding: 1;
    }
    HistoryScreen #hist-detail-info {
        height: auto;
        padding: 1;
        background: $surface;
        border: round $accent;
    }
    """

    def __init__(
        self,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self._entries = []

    def compose(self) -> ComposeResult:
        # List phase
        with Vertical(id="hist-list-phase"):
            yield Static(
                "[dim]Nenhum historico de execucao.[/dim]",
                id="hist-empty",
            )
            yield DataTable(id="hist-table")

        # Detail phase
        with Vertical(id="hist-detail-phase"):
            yield Static("", id="hist-detail-info")

    def on_mount(self) -> None:
        self.query_one("#hist-detail-phase").display = False
        self._load_history()

    def _load_history(self) -> None:
        """Load and display history entries."""
        from dbqm.core.history import load_history

        entries = load_history()
        self._entries = entries[:50]

        empty = self.query_one("#hist-empty", Static)
        table = self.query_one("#hist-table", DataTable)

        if not self._entries:
            empty.display = True
            table.display = False
            return

        empty.display = False
        table.display = True

        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column("#", key="num", width=4)
        table.add_column("Data/Hora", key="timestamp", width=20)
        table.add_column("Tipo", key="type", width=8)
        table.add_column("Nome", key="name")
        table.add_column("Conexao", key="conn")
        table.add_column("Resultado", key="result")
        table.add_column("Tempo", key="time", width=8)

        for i, e in enumerate(self._entries, 1):
            if e.entry_type == "group":
                tipo = "grupo"
                if e.all_match is True:
                    resultado = "OK"
                elif e.all_match is False:
                    resultado = "DIFF"
                else:
                    resultado = "-"
            else:
                tipo = "query"
                if e.success:
                    resultado = f"{e.row_count} rows"
                else:
                    resultado = "ERRO"

            table.add_row(
                str(i),
                e.timestamp,
                tipo,
                e.name,
                e.connection or "-",
                resultado,
                f"{e.elapsed:.1f}s",
                key=str(i),
            )

        # Set up action bar
        self._set_list_actions()

    def _set_list_actions(self) -> None:
        actions = [
            Action("Ver detalhes", "D", "hist_detail"),
            Action("Limpar historico", "X", "hist_clear"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Row selection — show detail
    # ------------------------------------------------------------------

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id != "hist-table":
            return
        key = event.row_key.value
        try:
            idx = int(key) - 1
        except (ValueError, TypeError):
            return
        if 0 <= idx < len(self._entries):
            self._show_detail(self._entries[idx])

    def _show_detail(self, entry) -> None:
        """Show details of a history entry."""
        self.query_one("#hist-list-phase").display = False
        detail_phase = self.query_one("#hist-detail-phase")
        detail_phase.display = True

        lines = []
        lines.append(f"[bold]Tipo:[/bold] {entry.entry_type}")
        lines.append(f"[bold]Nome:[/bold] {entry.name}")
        lines.append(f"[bold]Data:[/bold] {entry.timestamp}")
        if entry.connection:
            lines.append(f"[bold]Conexao:[/bold] {entry.connection}")
        if entry.params:
            for k, v in entry.params.items():
                lines.append(f"[bold]{k}:[/bold] {v}")
        lines.append(f"[bold]Tempo:[/bold] {entry.elapsed:.2f}s")

        if entry.entry_type == "query":
            lines.append(f"[bold]Registros:[/bold] {entry.row_count}")
            lines.append(
                f"[bold]Sucesso:[/bold] {'Sim' if entry.success else 'Nao'}"
            )
            if entry.error:
                lines.append(f"[bold]Erro:[/bold] {entry.error}")
        elif entry.entry_type == "group":
            if entry.all_match is not None:
                status = (
                    "[green]CONSISTENTE[/green]"
                    if entry.all_match
                    else "[red]DIVERGENTE[/red]"
                )
                lines.append(f"[bold]Resultado:[/bold] {status}")
            if entry.summary:
                lines.append(f"[bold]Resumo:[/bold] {entry.summary}")

        detail_info = self.query_one("#hist-detail-info", Static)
        detail_info.update("\n".join(lines))

        # Action bar
        actions = [
            Action("Voltar", "Esc", "hist_back"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Clear history
    # ------------------------------------------------------------------

    def _handle_clear(self) -> None:
        """Clear history with confirmation."""
        from dbqm.ui.modals.confirm import ConfirmModal

        modal = ConfirmModal(
            message="Limpar todo o historico de execucoes?",
            title="Limpar Historico",
        )
        self.app.push_screen(modal, callback=self._on_clear_confirmed)

    def _on_clear_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            return

        from dbqm.core.history import clear_history

        clear_history()
        self.notify("Historico limpo!", timeout=5)
        self._load_history()

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "hist_detail":
            # Use cursor position from table
            table = self.query_one("#hist-table", DataTable)
            if table.cursor_row is not None and table.row_count > 0:
                idx = table.cursor_row
                if 0 <= idx < len(self._entries):
                    self._show_detail(self._entries[idx])
        elif action == "hist_clear":
            self._handle_clear()
        elif action == "hist_back":
            self.go_back_to_list()

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def go_back_to_list(self) -> None:
        """Return to the history list."""
        self.query_one("#hist-list-phase").display = True
        self.query_one("#hist-detail-phase").display = False
        self._set_list_actions()
