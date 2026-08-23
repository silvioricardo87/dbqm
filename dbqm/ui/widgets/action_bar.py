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
    """A single-line bar showing contextual actions.

    Actions are accessible in two ways:
    - Pressing the shortcut key (N, T, E...) from anywhere (handled by App.on_key)
    - Clicking the action text
    """

    can_focus = False

    DEFAULT_CSS = """
    ActionBar {
        height: auto;
        padding: 0 1;
        background: $surface;
        border-top: solid $borda;
        dock: bottom;
        /* A linha que a StatusBar ocupa. O Textual NAO empilha irmaos
           docados na mesma borda: `_arrange_dock_widgets` poe cada um em
           `height - widget_height` e reserva `max(...)` — os dois caem no
           mesmo canto de baixo e quem e desenhado por ultimo cobre o
           outro. Era o que acontecia aqui desde sempre: a barra media duas
           linhas (regua + texto), a StatusBar pintava por cima da segunda
           e o unico vestigio das acoes na tela era a regua. Nenhum teste
           via: todos afirmavam sobre `_actions`, e nao sobre o pintado. */
        margin-bottom: 1;
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
            self.display = False
            return
        self.display = True
        parts: list[str] = []
        for action in self._actions:
            if not action.key and not action.label:
                continue
            if action.key:
                parts.append(
                    f"[@click=select_action('{action.action_id}')]"
                    f"[bold $primary]{action.key}[/] {action.label}"
                    f"[/]"
                )
            else:
                parts.append(f"[dim]{action.label}[/]")
        self.update("  ".join(parts))

    def action_select_action(self, action_id: str) -> None:
        """Handle click on an action."""
        self.post_message(ActionSelected(action_id))
