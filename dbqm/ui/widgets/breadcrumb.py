"""Breadcrumb navigation widget showing the current path."""

from __future__ import annotations

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static


class BreadcrumbNavigated(Message):
    """Posted when a non-terminal breadcrumb segment is clicked."""

    def __init__(self, index: int) -> None:
        self.index = index
        super().__init__()


class Breadcrumb(Static):
    """A single-line breadcrumb bar showing the navigation path."""

    can_focus = False

    DEFAULT_CSS = """
    Breadcrumb {
        height: 1;
        padding: 0 1;
        background: $surface;
    }
    """

    path: reactive[list[str]] = reactive(list, always_update=True)

    def set_path(self, segments: list[str]) -> None:
        """Set the breadcrumb path segments."""
        self.path = list(segments)

    def watch_path(self, path: list[str]) -> None:
        """Re-render when path changes."""
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the breadcrumb text."""
        if not self.path:
            self.update("")
            return
        parts: list[str] = []
        for i, segment in enumerate(self.path):
            if i > 0:
                parts.append("[dim] / [/dim]")
            if i < len(self.path) - 1:
                parts.append(
                    f"[@click=breadcrumb_navigate({i})][{segment}][/]"
                )
            else:
                parts.append(f"[bold bright_white]{segment}[/bold bright_white]")
        self.update("".join(parts))

    def action_breadcrumb_navigate(self, index: int) -> None:
        """Handle click on a breadcrumb segment."""
        self.post_message(BreadcrumbNavigated(index))

    def render_text(self) -> str:
        """Return plain text representation for testing."""
        return " / ".join(self.path) if self.path else ""
