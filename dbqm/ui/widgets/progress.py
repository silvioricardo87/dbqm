"""Progress indicator widget for long-running operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import LoadingIndicator, Static


class ProgressIndicator(Vertical):
    """A compact progress indicator with a message and loading animation.

    Hidden by default. Call ``start(message)`` to show it and ``stop()`` to
    hide it again.
    """

    DEFAULT_CSS = """
    ProgressIndicator {
        display: none;
        height: auto;
        max-height: 3;
        padding: 0 1;
    }

    ProgressIndicator Static {
        height: 1;
        content-align: center middle;
        text-align: center;
    }

    ProgressIndicator LoadingIndicator {
        height: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="progress-message")
        yield LoadingIndicator()

    def start(self, message: str) -> None:
        """Show the indicator with *message*."""
        self.query_one("#progress-message", Static).update(message)
        self.display = True

    def stop(self) -> None:
        """Hide the indicator."""
        self.display = False

    def update_message(self, message: str) -> None:
        """Update the displayed message while the indicator is visible."""
        self.query_one("#progress-message", Static).update(message)
