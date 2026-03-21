"""Contextual action bar widget."""

from __future__ import annotations

from collections import namedtuple

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button

Action = namedtuple("Action", ["label", "key", "action_id"])


class ActionSelected(Message):
    """Posted when an action is selected."""

    def __init__(self, action_id: str) -> None:
        self.action_id = action_id
        super().__init__()


class _ActionButton(Button):
    """A single action button with a shortcut key displayed."""

    DEFAULT_CSS = """
    _ActionButton {
        min-width: 6;
        height: 1;
        margin: 0 1 0 0;
        background: $surface-lighten-1;
        color: $text;
        border: none;
        padding: 0 1;
    }
    _ActionButton:hover {
        background: $primary 30%;
    }
    _ActionButton:focus {
        background: $primary 40%;
        text-style: bold;
    }
    """

    def __init__(self, action: Action) -> None:
        label = f"[{action.key}] {action.label}" if action.key else action.label
        super().__init__(label, id=f"ab-{action.action_id}")
        self.action = action


class ActionBar(Horizontal):
    """A bar showing contextual action buttons, navigable via Tab and arrow keys."""

    DEFAULT_CSS = """
    ActionBar {
        height: auto;
        max-height: 2;
        padding: 0 1;
        background: $surface;
    }
    ActionBar.empty {
        height: 0;
        display: none;
    }
    """

    can_focus = False  # Container itself not focusable, but children (buttons) are

    def __init__(self) -> None:
        super().__init__()
        self._actions: list[Action] = []

    def set_actions(self, actions: list[Action]) -> None:
        """Set the list of available actions, rebuilding buttons."""
        self._actions = list(actions)
        self._rebuild()

    def _rebuild(self) -> None:
        """Rebuild the action bar buttons."""
        self.remove_children()
        if not self._actions:
            self.add_class("empty")
            return
        self.remove_class("empty")
        for action in self._actions:
            if action.key or action.label:  # Skip empty actions
                self.mount(_ActionButton(action))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button click — post ActionSelected."""
        if isinstance(event.button, _ActionButton):
            self.post_message(ActionSelected(event.button.action.action_id))
            event.stop()
