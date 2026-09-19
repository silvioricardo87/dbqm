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
        border-top: solid $ds-border;
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
        self._pinned_action: Action | None = None

    def set_actions(self, actions: list[Action]) -> None:
        """Set the list of available actions."""
        self._actions = list(actions)
        self._rebuild()

    def set_pinned_action(self, action: Action | None) -> None:
        """Pin one action at the end of the bar, which `set_actions` does not erase.

        It exists for a measured case: `ToolsScreen` announces `Esc Back` when it
        opens a tool, and the tool — `TemplateManageScreen`, say — calls
        `set_actions` in its own `on_mount`, AFTER. The announcement of the
        screen's only way out disappeared under `N New  E Edit  R Rename
        D Remove`. Before this phase there was a "Back" button inside the panel;
        it went away because a button does not navigate, and without the pin the
        screen would become a dead end for anyone who does not guess the key.

        ONE pinned action, not a list: it belongs to the container that hosts a
        whole screen, and there can only be one per tab. It is cleared by
        `DBQMApp.on_tabbed_content_tab_activated`, when the tab changes — without
        that, the action would leak into the other tabs, where it goes back
        nowhere.
        """
        self._pinned_action = action
        self._rebuild()

    def visible_actions(self) -> list[Action]:
        """What the bar actually draws, in order: the screen's, then the pinned one."""
        actions = list(self._actions)
        if self._pinned_action is not None:
            actions.append(self._pinned_action)
        return actions

    def _rebuild(self) -> None:
        """Rebuild the action bar content."""
        actions = self.visible_actions()
        if not actions:
            self.update("")
            self.display = False
            return
        self.display = True
        parts: list[str] = []
        for action in actions:
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
