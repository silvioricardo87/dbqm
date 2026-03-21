"""ResultTable widget — displays QueryResult data with pagination and vertical mode."""

from __future__ import annotations

import math
from typing import Any

from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Static

from dbqm.core.query_engine import QueryResult


class ResultTable(Vertical, can_focus=False):
    """Widget that wraps DataTable to display query results with pagination."""

    DEFAULT_CSS = """
    ResultTable {
        height: 1fr;
    }
    ResultTable DataTable {
        height: 1fr;
    }
    ResultTable .vertical-view {
        height: 1fr;
        overflow-y: auto;
    }
    """

    vertical_mode: reactive[bool] = reactive(False)
    current_page: reactive[int] = reactive(0)
    page_size: int = 100

    def __init__(
        self,
        *,
        page_size: int = 100,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(name=name, id=id, classes=classes)
        self.page_size = page_size
        self._result: QueryResult | None = None
        self._data_table = DataTable()
        self._vertical_view = Static("", classes="vertical-view")

    def compose(self):
        yield self._data_table
        yield self._vertical_view

    def focus(self, scroll_visible: bool = True) -> None:
        """Delegate focus to the internal DataTable."""
        try:
            self._data_table.focus(scroll_visible)
        except Exception:
            super().focus(scroll_visible)

    def on_mount(self) -> None:
        self._vertical_view.display = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def row_count(self) -> int:
        if self._result is None:
            return 0
        return self._result.row_count

    @property
    def total_pages(self) -> int:
        if self._result is None or self._result.row_count == 0:
            return 1
        return math.ceil(self._result.row_count / self.page_size)

    @property
    def page_info(self) -> str:
        page = self.current_page + 1
        total = self.total_pages
        count = self.row_count
        return f"Pagina {page}/{total} ({count} registros)"

    @property
    def result_info(self) -> str:
        if self._result is None:
            return ""
        return (
            f"{self._result.row_count} registros"
            f" | {self._result.elapsed:.2f}s"
            f" | {self._result.connection_name}"
        )

    def load_result(self, result: QueryResult) -> None:
        """Load a QueryResult into the table."""
        self._result = result
        self.current_page = 0
        self._refresh_view()

    def next_page(self) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._refresh_view()

    def prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1
            self._refresh_view()

    def toggle_vertical(self) -> None:
        self.vertical_mode = not self.vertical_mode
        self._refresh_view()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _current_page_rows(self) -> list[list[Any]]:
        if self._result is None:
            return []
        start = self.current_page * self.page_size
        end = start + self.page_size
        return self._result.rows[start:end]

    def _refresh_view(self) -> None:
        if self.vertical_mode:
            self._show_vertical()
        else:
            self._show_table()

    def _show_table(self) -> None:
        self._data_table.display = True
        self._vertical_view.display = False
        self._data_table.clear(columns=True)
        if self._result is None:
            return
        for col in self._result.columns:
            self._data_table.add_column(col, key=col)
        for row in self._current_page_rows():
            display_row = [str(v) if v is not None else "" for v in row]
            self._data_table.add_row(*display_row)

    def _show_vertical(self) -> None:
        self._data_table.display = False
        self._vertical_view.display = True
        if self._result is None:
            self._vertical_view.update("")
            return
        columns = self._result.columns
        if not columns:
            self._vertical_view.update("(sem resultados)")
            return
        rows = self._current_page_rows()
        if not rows:
            self._vertical_view.update("(sem resultados)")
            return
        max_col_len = max(len(c) for c in columns)
        blocks: list[str] = []
        base = self.current_page * self.page_size
        for i, row in enumerate(rows):
            lines = [f"*** Registro {base + i + 1} ***"]
            for col, val in zip(columns, row):
                display_val = str(val) if val is not None else ""
                lines.append(f"  {col:>{max_col_len}}: {display_val}")
            blocks.append("\n".join(lines))
        self._vertical_view.update("\n\n".join(blocks))
