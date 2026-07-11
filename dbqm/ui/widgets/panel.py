"""Reusable bordered Panel with the title placed inside the box.

Implements design guidelines 3 (continuous border, title inside), 4
(focus-within lighting), 5 (no nested borders). Corners use `border: round`.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widget import Widget
from textual.widgets import Label


class Panel(Vertical):
    DEFAULT_CSS = """
    Panel {
        border: round $border;
        background: $panel;
        height: 1fr;
        padding: 0;
    }
    Panel:focus-within { border: round $primary; }
    Panel.accent-focus:focus-within { border: round $accent; }

    Panel > #panel-title {
        height: 1;
        width: 100%;
        color: $primary;
        text-style: bold;
        background: $surface;
        border-bottom: solid $border;
        padding: 0 1;
    }
    Panel.accent-focus > #panel-title { color: $accent; }

    Panel > #panel-body {
        height: 1fr;
        padding: 1 1;
    }
    /* guideline 5: inner widgets carry no border of their own */
    Panel #panel-body DataTable,
    Panel #panel-body OptionList,
    Panel #panel-body ListView,
    Panel #panel-body TextArea,
    Panel #panel-body Input,
    Panel #panel-body Select { border: none; }
    """

    def __init__(self, title: str, *, accent: bool = False, id: str | None = None) -> None:
        super().__init__(id=id)
        self._title = title
        # NOTE: intentionally NOT named `_pending_children` — Textual's own
        # `Widget.__init__`/`Widget._compose()` already own an attribute with
        # that exact name and merge it with `compose(self)` results, mounting
        # everything as direct children of this Panel. Reusing that name here
        # would smuggle caller-yielded children in as siblings of
        # `#panel-title`/`#panel-body` instead of routing them into the body.
        self._panel_pending_children: list[Widget] = []
        if accent:
            self.add_class("accent-focus")

    def compose(self) -> ComposeResult:
        yield Label(self._title, id="panel-title")
        yield Vertical(id="panel-body")

    def compose_add_child(self, widget: Widget) -> None:
        # `compose_add_child` runs while this Panel itself is being composed,
        # before `#panel-body` exists in the DOM — so we cannot mount into it
        # yet. Stash caller-yielded children and route them once mounted.
        self._panel_pending_children.append(widget)

    def on_mount(self) -> None:
        if self._panel_pending_children:
            body = self.query_one("#panel-body", Vertical)
            body.mount(*self._panel_pending_children)
            self._panel_pending_children = []

    def set_title(self, title: str) -> None:
        self._title = title
        self.query_one("#panel-title", Label).update(title)
