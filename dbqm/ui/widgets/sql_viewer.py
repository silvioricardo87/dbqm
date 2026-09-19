"""Read-only SQL display widget with syntax highlighting."""
from __future__ import annotations

from typing import Any

from rich.syntax import Syntax
from textual.widgets import Static


class SqlViewer(Static):
    """A read-only SQL display widget with syntax highlighting.

    Uses Rich's Syntax object for monokai-themed SQL highlighting.

    It draws no frame of its own. The three places that mount it already put
    it inside one: `Panel("RESULTS")` in the ad-hoc screen, `Panel("DATA")` in
    the browser, and a `Dialog` in `SqlViewerModal`. The `border: round
    $accent` it used to carry was a box inside a box in all three — exactly
    what `Panel`'s guideline 5 zeroes out for DataTable/OptionList/TextArea/
    Input/Select, and which only missed it because it is a `Static`.
    """

    DEFAULT_CSS = """
    SqlViewer {
        height: auto;
        max-height: 20;
        overflow-y: auto;
        padding: 1;
    }
    """

    def __init__(self, sql: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._sql = sql

    def on_mount(self) -> None:
        if self._sql:
            self._render_sql()

    def set_sql(self, sql: str) -> None:
        """Set and render the SQL content."""
        self._sql = sql
        self._render_sql()

    def _render_sql(self) -> None:
        syntax = Syntax(
            self._sql,
            lexer="sql",
            theme="monokai",
            line_numbers=True,
            word_wrap=True,
        )
        self.update(syntax)
