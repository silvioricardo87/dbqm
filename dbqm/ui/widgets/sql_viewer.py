"""Read-only SQL display widget with syntax highlighting."""
from __future__ import annotations

from rich.syntax import Syntax
from textual.widgets import Static


class SqlViewer(Static):
    """A read-only SQL display widget with syntax highlighting.

    Uses Rich's Syntax object for monokai-themed SQL highlighting.
    """

    DEFAULT_CSS = """
    SqlViewer {
        height: auto;
        max-height: 20;
        overflow-y: auto;
        border: round $accent;
        padding: 1;
    }
    """

    def __init__(self, sql: str = "", **kwargs) -> None:
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
