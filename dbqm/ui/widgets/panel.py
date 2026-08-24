"""Reusable bordered Panel with the title placed inside the box.

Implements design guidelines 3 (continuous border, title inside), 4
(focus-within lighting), 5 (no nested borders). Corners use `border: round`.
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.css.scalar import Unit
from textual.widget import Widget
from textual.widgets import Label


class Panel(Vertical):
    #: Lines the chrome consumes before the body: 2 of border (top and
    #: bottom) + 1 of title + 1 of the title's `border-bottom` rule.
    CHROME = 4

    DEFAULT_CSS = """
    Panel {
        border: round $ds-border;
        background: $panel;
        height: 1fr;
        padding: 0;
    }
    Panel:focus-within { border: round $primary; }
    Panel.accent-focus:focus-within { border: round $accent; }

    Panel > #panel-title {
        height: auto;
        width: 100%;
        color: $primary;
        text-style: bold;
        background: $surface;
        border-bottom: solid $ds-border;
        padding: 0 1;
    }
    Panel.accent-focus > #panel-title { color: $accent; }

    Panel > #panel-body {
        /* `1fr` is the common case: the panel is given a height and the
           body fills it. When the PANEL ITSELF asks for `height: auto`
           this `1fr` becomes the silent lie described in `_adjust_body`,
           and the `-content` class (just below) takes its place. */
        height: 1fr;
        padding: 1 1;
        /* VISIBLE vertical overflow: a panel taller than the box scrolls,
           instead of clipping in silence. The Oracle Instant Client
           section of Configuracoes was born at y=39 of a body that did
           not scroll — there was no way to reach it in a 24-line
           terminal. `auto` and not `scroll` on purpose: when the child
           takes `1fr` (DataTable, OptionList) nothing overflows, no bar
           appears and no nested scrolling is created on top of the
           widget's own. */
        overflow-y: auto;
    }
    /* Density: body without the VERTICAL padding (the horizontal one stays
       — it is what separates the text from the border). Two lines per panel
       is cheap when there is one panel on the screen and expensive when
       there are six: Configuracoes spent 12 lines out of 24 on air. It is a
       COMPONENT DECISION, with a name, and not a `#panel-body { padding: 0
       1 }` rewritten in every screen that needs it — the second such copy
       had already shown up, and "each screen decides for itself" is exactly
       what section 4 of the grammar exists to remove. */
    Panel.-dense > #panel-body { padding: 0 1; }
    /* Turned on by `_adjust_body` when the panel itself asks for
       `height: auto`. A class, and not writing the height directly into
       `styles`, because `dbqm/ui` has a guard against that kind of write
       outside the component (the size of a `Dialog` may only be decided
       inside `dialog.py`) — punching through that guard to solve this
       problem would be trading one silence for another. */
    Panel > #panel-body.-content { height: auto; }
    /* guideline 5: inner widgets carry no border of their own */
    Panel #panel-body DataTable,
    Panel #panel-body OptionList,
    Panel #panel-body TextArea,
    Panel #panel-body Input,
    Panel #panel-body Select { border: none; }
    """

    def __init__(
        self,
        title: str,
        *,
        accent: bool = False,
        dense: bool = False,
        id: str | None = None,
    ) -> None:
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
        if dense:
            self.add_class("-dense")

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
        self._adjust_body()

    def _adjust_body(self) -> None:
        """Makes `height: auto` on the panel really mean "the size of the content".

        `#panel-body` is born with `height: 1fr`. A `1fr` inside a parent of
        automatic height does not measure the content: it stretches up to the
        height of the panel's CONTAINER. The effect is that
        `Panel { height: auto }` never worked — and it failed in SILENCE,
        which is the real problem. Three panels of three lines each, in a
        24-line terminal:

            Vertical height:auto -> height=6  each, y=1 / y=8  / y=15
            Panel    height:auto -> height=24 each, y=1 / y=24 / y=47

        The last two sections are born below the fold without anything in the
        CSS looking wrong. That is why the body switches to `auto` when the
        panel asked for `auto`: the declaration comes to do what it says.
        Reading `self.styles.height` (and not an explicit modifier such as
        `Panel.-content`) is what keeps the rule valid for whoever writes
        ordinary CSS — nobody needs to know a rule exists.

        `max-height` together with `auto` needs the arithmetic: a body in
        `auto` does not see the parent's ceiling, and `max-height: 100%` on
        the body would be off by `CHROME` lines (a percentage resolves
        against the WHOLE parent, title included) — the body would be born
        taller than the box and the last lines would be clipped, out of the
        scrolling's reach. Subtracting `CHROME` makes the body fit exactly
        and the excess SCROLL, visibly. A ceiling in a unit other than cells
        does not have this arithmetic: in that case the body stays at `1fr`,
        which fills the box and scrolls — it never clips.

        `tests/design/test_vertical_overflow.py` renders the three cases
        and fails if the coupling is lost. It is the reason this cannot go
        back to failing quietly.
        """
        altura = self.styles.height
        if altura is None or not altura.is_auto:
            return
        corpo = self.query_one("#panel-body", Vertical)
        teto = self.styles.max_height
        if teto is not None:
            if teto.unit is not Unit.CELLS:
                return
            corpo.styles.max_height = max(int(teto.value) - self.CHROME, 1)
        corpo.add_class("-content")

    @property
    def body(self) -> Vertical:
        """The container where the panel's content lives.

        `compose_add_child` only routes what the caller yields inside
        `with Panel(...)`. RUNTIME mounting (`panel.mount(...)`, as the
        filter bar and the list of `query_exec`/`group_run` do) does not go
        through it and would land as a SIBLING of `#panel-title`/
        `#panel-body`, outside the chrome. Whoever mounts after compose
        mounts here.
        """
        return self.query_one("#panel-body", Vertical)

    def set_title(self, title: str) -> None:
        self._title = title
        self.query_one("#panel-title", Label).update(title)
