"""Progress indicator widget for long-running operations."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import LoadingIndicator, Static


class ProgressIndicator(Vertical, can_focus=False):
    """A compact progress indicator with a message and loading animation.

    Hidden by default. Call ``start(message)`` to show it and ``stop()`` to
    hide it again.

    A DELIBERATE EXCEPTION to "every screen is made of panels; nothing floats
    on the background" (section 4 of the layout grammar). The seven screens
    that use it render `ProgressIndicator()` LOOSE, a sibling of the panels
    rather than a child of one. Two reasons, in this order:

    1. It is not a section — it is the state of the WHOLE screen while a
       remote operation runs. Framing it would create a panel that appears and
       disappears, and the frame would start meaning two different things.
    2. Framed, it would inherit the visibility of whatever panel hosted it —
       and the screens that use it change phase by hiding panels. In
       `exec_routine` the indicator lights up with `#er-select-phase` on
       screen and only goes out when `_show_objects` hides that phase: inside
       it, the only sign that the remote call is running would vanish along
       with the phase.

    The same exemption covers `#pe-empty` (the package editor's
    "loading/cancelled" text), for reason (1): it is the state of the screen,
    not a section of it.
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
