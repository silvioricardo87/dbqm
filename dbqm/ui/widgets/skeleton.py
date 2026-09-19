"""A loading skeleton: the shape of the content that is coming.

A centred spinner says nothing about what is arriving and lets the layout
jump when the content lands. The skeleton reserves the right space:
`lines` x `columns` of blocks, in the shape of the table that will replace
it.

Closed on purpose, in the same spirit as `dialog.py`/`verdict.py`: the
only two degrees of freedom are `lines` and `columns`, both integers —
there is no style variant to override. A caller who needs another
appearance needs a new widget, never `skeleton.styles.*` after
construction; ``test_dialog_has_no_style_override_outside_the_component``
(a sweep for `.styles.(width|height) =` across all of `dbqm/ui/`) already
closes that door for every widget, this one included.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Static


class Skeleton(Vertical):
    """A placeholder shaped like a table of `lines` x `columns`."""

    DEFAULT_CSS = """
    Skeleton { height: auto; width: 100%; }
    Skeleton .skeleton-row { height: 1; width: 100%; }
    Skeleton .skeleton-cell {
        height: 1;
        width: 1fr;
        margin: 0 1 0 0;
        background: $ds-surface-raised;
    }
    """

    def __init__(
        self,
        rows: int = 5,
        columns: int = 4,
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._rows = rows
        self._columns = columns

    def compose(self) -> ComposeResult:
        for _ in range(self._rows):
            with Horizontal(classes="skeleton-row"):
                for _ in range(self._columns):
                    yield Static("", classes="skeleton-cell")
