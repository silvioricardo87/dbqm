"""Contextual action bar widget."""

from __future__ import annotations

from collections import namedtuple

from textual.message import Message
from textual.widgets import Static

Action = namedtuple("Action", ["label", "key", "action_id"])


class ActionSelected(Message):
    """Posted when an action is selected."""

    def __init__(self, action_id: str) -> None:
        self.action_id = action_id
        super().__init__()


class ActionBar(Static):
    """A single-line bar showing contextual action buttons."""

    DEFAULT_CSS = """
    ActionBar {
        height: auto;
        padding: 0 1;
        background: $surface;
    }
    """

    def __init__(self) -> None:
        super().__init__("")
        self._actions: list[Action] = []

    def set_actions(self, actions: list[Action]) -> None:
        """Set the list of available actions."""
        self._actions = list(actions)
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the action bar content."""
        if not self._actions:
            self.update("")
            self.styles.height = 0
            return
        self.styles.height = 1
        parts: list[str] = []
        for action in self._actions:
            parts.append(
                f"[@click=select_action('{action.action_id}')]"
                f"[bold][{action.key}][/bold] {action.label}"
                f"[/]"
            )
        self.update("  ".join(parts))

    def action_select_action(self, action_id: str) -> None:
        """Handle click on an action."""
        self.post_message(ActionSelected(action_id))

    def render_text(self) -> str:
        """Return plain text representation for testing."""
        if not self._actions:
            return ""
        return "  ".join(
            f"[{a.key}] {a.label}" for a in self._actions
        )
