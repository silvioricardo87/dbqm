"""Dialog: the layer that floats over the content.

It exists because the same `border: thick $accent` block was copied 29 times
across 13 files. Rule of use: if it floats over the content, it is a Dialog;
if it does not float, it is a Panel.

The `width` variants are closed on purpose. If a case needs something outside
them, that is a new variant missing from the system — never a local exception
(`dialog.styles.width = ...` after construction). The local exception is how
the system dies: silently, one case at a time, and without `__init__`'s
validation seeing anything, because the write happens after it.
`tests/ui/test_widgets.py::test_dialog_has_no_style_override_
outside_the_component` closes that door.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import Static

# "sm"/"md"/"lg" are fixed-width columns (a number of cells) — compact
# text/form dialogs. "screen" is the documented exception: dialogs that exist
# to DISPLAY content (a result table, rendered text) need to fill most of the
# viewport, so the unit changes to a percentage. Mixing cells and percentages
# without saying so would be the same lie as a luminance step out of order —
# hence this comment.
WIDTHS: dict[str, int | str] = {"sm": 50, "md": 70, "lg": 90, "screen": "90%"}
TONES: tuple[str, ...] = ("neutral", "destructive")

# Height used only by the "screen" variant — the others keep DEFAULT_CSS's
# `height: auto; max-height: 90%`, which is enough for short content. A single
# height for the two cases that ask for "screen" today: the difference between
# 80% and 85% between them was never a decision, just a copy.
_SCREEN_HEIGHT = "85%"


class Dialog(Vertical):
    """Chrome of a floating layer: frame, title and content area."""

    DEFAULT_CSS = """
    Dialog {
        width: auto;
        height: auto;
        max-height: 90%;
        background: $ds-panel;
        border: thick $ds-border-strong;
        padding: 1 2;
    }
    Dialog.-destructive { border: thick $ds-op-failure; }
    Dialog .dialog-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        title: str,
        *,
        width: str = "md",
        tone: str = "neutral",
        id: str | None = None,
    ) -> None:
        if width not in WIDTHS:
            raise ValueError(f"largura desconhecida: {width!r}; use {sorted(WIDTHS)}")
        if tone not in TONES:
            raise ValueError(f"tom desconhecido: {tone!r}; use {list(TONES)}")
        super().__init__(id=id, classes=f"-{tone}")
        self._title = title
        self.styles.width = WIDTHS[width]
        if width == "screen":
            self.styles.height = _SCREEN_HEIGHT

    def compose(self) -> ComposeResult:
        # Verified in this version of Textual: the widget's own compose and
        # the children passed via `with Dialog(...)` coexist, in this order.
        yield Static(self._title, classes="dialog-title", id=f"{self.id}-title")
