"""History screen — browse execution history."""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.content import Content
from textual.widgets import Button, DataTable, Static

from dbqm.i18n import t
from dbqm.ui.widgets.action_bar import Action, ActionBar, ActionSelected
from dbqm.ui.widgets.empty_state import EmptyState
from dbqm.ui.widgets.panel import Panel
from dbqm.ui.widgets.verdict import mark_operation, mark_verdict


class HistoryScreen(Vertical):
    """Screen widget for browsing execution history.

    Shows a DataTable with the last 50 history entries and a docked
    detail panel below it that updates live as the row highlight moves.
    """

    DEFAULT_CSS = """
    HistoryScreen {
        height: 1fr;
    }
    HistoryScreen #hist-list-panel {
        height: 2fr;
    }
    HistoryScreen #hist-empty {
        height: auto;
    }
    HistoryScreen #hist-table {
        height: 1fr;
    }
    /* The list is the subject; the detail is a companion to whatever row is
       highlighted. An even 1fr/1fr split with `min-height: 8` on the detail
       inverted that: measured inside the real DBQMApp at 80x24 — the size most
       people run — the tab strip, status bar and action bar leave about eleven
       rows for the two panels, the detail claimed eight of them, and the table
       was left a THREE-row viewport showing 2 of 30 entries.

       A bare test harness hands the screen the full 24 rows and reports a
       nine-row viewport, which is why this looked fine for so long. Measure in
       the real app. */
    HistoryScreen #hist-list-panel {
        height: 2fr;
        min-height: 7;
    }
    HistoryScreen #hist-detail-panel {
        height: 1fr;
        min-height: 4;
        max-height: 9;
    }
    HistoryScreen #hist-detail {
        height: 1fr;
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
        with Panel(t("panel.history"), id="hist-list-panel"):
            yield EmptyState(
                what=t("history.list_title"),
                why=t("history.empty_why"),
                action_label=t("history.run_query"),
                action_id="executar-consulta",
                id="hist-empty",
            )
            yield DataTable(id="hist-table")

        with Panel(t("panel.details"), id="hist-detail-panel"):
            yield Static("", id="hist-detail")

    def on_mount(self) -> None:
        self._reload()
        self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        """Focus what the screen is SHOWING.

        With an empty history what is on screen is the `EmptyState`, and the
        only actionable thing in it is the button. Focusing the table at
        that point put the focus on a hidden widget: nothing visible was
        marked, and the Enter key did not reach the way out the screen had
        just offered.
        """
        table = self.query_one("#hist-table", DataTable)
        if table.display:
            table.focus()
            return
        try:
            self.query_one("#hist-empty", EmptyState).query_one(Button).focus()
        except Exception:
            pass

    def _reload(self) -> None:
        """Load and display history entries."""
        from dbqm.core.history import load_history

        entries = load_history()
        self._entries = entries[:50]

        empty = self.query_one("#hist-empty", EmptyState)
        table = self.query_one("#hist-table", DataTable)
        detail_panel = self.query_one("#hist-detail-panel")

        table.clear(columns=True)
        table.cursor_type = "row"
        table.add_column(t("common.date"), key="timestamp", width=20)
        table.add_column(t("common.connection"), key="conn")
        table.add_column(t("common.type"), key="type", width=8)
        table.add_column("SQL", key="sql")
        table.add_column(t("common.time"), key="time", width=8)
        table.add_column(t("common.status"), key="status", width=10)

        if not self._entries:
            # Hiding the table is what the other ten empty lists in dbqm
            # already did (`connections`, `query_list`, `browser`, ...):
            # without it, the `Data Conexao Tipo SQL Tempo Status` header was
            # painted right against the empty state, promising a table that
            # does not exist. The DETAIL panel goes away for the same reason
            # — there is no record to detail — and giving its 8 lines back to
            # the panel above is what makes the identity line (`Historico`)
            # fit at 80x24, where before it was clipped entirely.
            empty.display = True
            table.display = False
            detail_panel.display = False
            self._show_detail(None)
            self._set_list_actions()
            return

        empty.display = False
        table.display = True
        detail_panel.display = True

        for i, e in enumerate(self._entries, 1):
            if e.entry_type == "group":
                tipo = "grupo"
                if e.all_match is True:
                    status = mark_verdict("match")
                elif e.all_match is False:
                    status = mark_verdict("diff")
                else:
                    status = "-"
            else:
                tipo = "query"
                status = mark_operation("ok") if e.success else mark_operation("failure")

            table.add_row(
                str(e.timestamp) if e.timestamp else "",
                str(e.connection) if e.connection else "-",
                tipo,
                str(e.name) if e.name else "",
                f"{e.elapsed:.1f}s",
                # DataTable formats string cells with Rich's plain parser,
                # which does not know about `$token` (only Textual's content
                # markup does). Content.from_markup resolves the token before
                # the cell gets there.
                Content.from_markup(status),
                key=str(i),
            )

        self._set_list_actions()
        self._show_detail(self._entries[0])

    def _set_list_actions(self) -> None:
        actions = [
            Action(t("history.clear_action"), "X", "hist_clear"),
        ]
        try:
            self.app.query_one(ActionBar).set_actions(actions)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Row highlight — live-update the docked detail panel
    # ------------------------------------------------------------------

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.data_table.id != "hist-table":
            return
        if event.row_key is None or event.row_key.value is None:
            return
        try:
            idx = int(event.row_key.value) - 1
        except (ValueError, TypeError):
            return
        if 0 <= idx < len(self._entries):
            self._show_detail(self._entries[idx])

    def _show_detail(self, entry) -> None:
        """Render details of a history entry into the docked detail panel."""
        detail = self.query_one("#hist-detail", Static)

        if entry is None:
            detail.update(f'[dim]{t("history.nothing_selected")}[/dim]')
            return

        lines = []
        lines.append(f'[bold]{t("common.type")}:[/bold] {entry.entry_type}')
        lines.append(f'[bold]{t("common.name")}:[/bold] {entry.name}')
        lines.append(f'[bold]{t("common.date")}:[/bold] {entry.timestamp}')
        if entry.connection:
            lines.append(f'[bold]{t("common.connection")}:[/bold] {entry.connection}')
        if entry.params:
            for k, v in entry.params.items():
                lines.append(f"[bold]{str(k)}:[/bold] {str(v)}")
        lines.append(f'[bold]{t("common.time")}:[/bold] {entry.elapsed:.2f}s')

        if entry.entry_type == "query":
            lines.append(f'[bold]{t("common.rows")}:[/bold] {entry.row_count}')
            lines.append(
                f'[bold]{t("common.success")}:[/bold] '
                f'{t("common.yes") if entry.success else t("common.no")}'
            )
            if entry.error:
                lines.append(f'[bold]{t("common.error")}:[/bold] {str(entry.error)}')
        elif entry.entry_type == "group":
            if entry.all_match is not None:
                status = mark_verdict(
                    "match" if entry.all_match else "diff",
                    label=(t("verdict.consistent") if entry.all_match
                           else t("verdict.divergent")),
                )
                lines.append(f'[bold]{t("export.label_result")}:[/bold] {status}')
            if entry.summary:
                lines.append(f'[bold]{t("history.summary")}:[/bold] {str(entry.summary)}')

        detail.update("\n".join(lines))

    # ------------------------------------------------------------------
    # Clear history
    # ------------------------------------------------------------------

    def _handle_clear(self) -> None:
        """Clear history with confirmation."""
        from dbqm.ui.modals.confirm import ConfirmModal

        modal = ConfirmModal(
            message=t("history.confirm_clear"),
            title=t("history.confirm_clear_title"),
        )
        self.app.push_screen(modal, callback=self._on_clear_confirmed)

    def _on_clear_confirmed(self, confirmed: bool) -> None:
        if not confirmed:
            # Stay on the history screen, restore focus
            self._set_initial_focus()
            return

        from dbqm.core.history import clear_history

        clear_history()
        self.notify(t("history.cleared_notice"), timeout=5)
        self._reload()
        # Clearing leaves the screen empty: the focus has to follow the
        # table that has just left the stage, otherwise it stays on a hidden
        # widget.
        self._set_initial_focus()

    # ------------------------------------------------------------------
    # Action bar handlers
    # ------------------------------------------------------------------

    def on_action_selected(self, message: ActionSelected) -> None:
        action = message.action_id

        if action == "hist_clear":
            self._handle_clear()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "executar-consulta":
            # Guarded: HistoryScreen is also mounted standalone in tests,
            # where self.app has no action_switch_tab (that lives on
            # DBQMApp only).
            switch = getattr(self.app, "action_switch_tab", None)
            if callable(switch):
                switch("tab-consultas")
