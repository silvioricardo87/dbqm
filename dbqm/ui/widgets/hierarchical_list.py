r"""hierarchical_item — list item with a hierarchy of up to three lines.

The problem this component solves (layout grammar, Task 3): a list of
connections with more than two lines became illegible because identity and
metadata fought over the same line — `connections.py` assembled
`name (type - target) | description` as a single string, the list wrapped that
string wherever it fit in the available width, and without visual hierarchy the
eye could not tell a continuation from a new entry. `query_list.py` had the same
problem and a patch on top of it: truncating the description at 35 characters
with the comment "keep line readable".

The cure is not a separator — it is hierarchy. Each line says what it is by
color, not by punctuation:
  1. identity — what the person is looking for, in bold, alone.
  2. disambiguation — type, target, connection; indented, in $ds-text-muted.
  3. context — description; indented, in $ds-text-disabled; optional.

Empty lines are omitted, not rendered blank: an item with identity only ends
up with a single line, not with two ghost lines.

A connection name and a description are user data, and the text is free — an
environment tag (`Proposta [PROD]`) or a ticket reference with brackets is a
plausible pattern in this domain. That is why the `Content` is assembled
programmatically with `Content.assemble`/`(text, style)` tuples, never passing
the user data through the markup parser (`Content.from_markup`/`[tag]...[/]`):
the parser never sees the text, so there is nothing to interpret as a tag and
nothing to escape. This avoids at the root the known asymmetry of Textual's
parser between `\[` and `\]` (documented in `result_table.py`, where the width
compensation was built on top of that behaviour) without touching
`escape_markup` — which is shared with six other callers and is not used here.

Alongside the `Content`, the module delivers the `wrap_width` /
`wrap_lines` pair, which is what makes the hierarchy true for long
text: without pre-breaking on `\n`, the continuation of an over-wide line
goes back to column 0 — the identity column of the NEXT entry — and the
defect reappears in full. The arithmetic lives here, and not in each
screen, because it only depends on the CSS of `Panel`/`OptionList`; the
panel width is what stays with the screen.

And it also delivers `NamedOption` — the `Option` that carries this content
into the `OptionList` holding the item's name as data, and not as an `id`.
The reason is in the class docstring.
"""
from __future__ import annotations

import textwrap

from textual.content import Content
from textual.widgets.option_list import Option

_INDENT = "  "


# ----------------------------------------------------------------------
# Wrap width — the arithmetic that every caller that pre-wraps text
# needs to do, in a single place.
#
# Whoever pre-wraps (see `wrap_lines` and the docstring of
# `hierarchical_item`) needs to know how many columns are left for the
# TEXT inside an `OptionList` that lives in a `Panel`. Each part below is
# read from the CSS that declares it, none measured at runtime:
#
#   - `Panel` (dbqm/ui/widgets/panel.py): `border: round` = 1 column on
#     each side.
#   - `Panel > #panel-body`: `padding: 1 1` = 1 column on each side
#     (vertical, horizontal); the horizontal one is what matters here.
#   - `OptionList` (textual.widgets, DEFAULT_CSS): `padding: 0 1` = 1
#     column on each side; its own border (`border: tall`) is zeroed out
#     by `Panel #panel-body OptionList { border: none; }`, so it does not
#     enter this arithmetic.
#
# Each "on each side" counts as 2 (left + right).
_PANEL_BORDER = 2
_PANEL_BODY_PADDING = 2
_OPTION_LIST_PADDING = 2

# The OptionList's vertical scrollbar — 2 columns, Textual's own default
# (`Widget().styles.scrollbar_size_vertical == 2`; none of the lists
# overrides `scrollbar-size-vertical`, so the default applies). It only
# appears when the list overflows vertically, which depends on how many
# items exist — outside the control of whoever builds the screen.
# Subtracted UNCONDITIONALLY: the worst case (a scrollable list) is the
# common case in real use, and not subtracting it means the computed width
# is only right for a list too short to scroll.
#
# This is the part that cost four rounds on the Conexoes list, and the
# reason lies in the asymmetry of Textual's API: `content_region` does NOT
# subtract the scrollbar, `scrollable_content_region` does. A width
# derived from `content_region` measured on a short list passes in tests
# and comes out wrong in use — that is how the "...ambiente" line came out
# without an indent, aligned with the identity column of the next entry.
# Whoever re-verifies this arithmetic: measure it with the list REALLY
# scrolling (`show_vertical_scrollbar is True`) and read
# `scrollable_content_region`.
_VERTICAL_SCROLLBAR = 2

# The indent that `_indented_field` prepends to EVERY disambiguation/
# context line. It enters the arithmetic because the useful width is the
# text's, not the line's: pre-wrapping at N columns and then adding the
# indent gives back lines of N+2 columns, which is exactly 2 more than
# fits.
_CONTEXT_INDENT = len(_INDENT)


def wrap_width(panel_width: int) -> int:
    """TEXT columns available in a list item, given the panel.

    Takes the width of the `Panel` that hosts the `OptionList` (the value
    the screen's CSS declares) and returns what is left for the text after
    the Panel border, the body padding, the OptionList padding, the
    scrollbar (worst case) and the indent the line itself pays.

    The panel width STAYS WITH THE SCREEN — Conexoes and Consultas have
    panels of different sizes and that is how it should be (one is the
    left column of a master-detail, the other is the whole screen). What
    is shared is the DERIVATION, which only depends on the CSS of `Panel`
    and `OptionList` and is identical in both places — duplicating it
    would open room for the two copies to diverge when that CSS changes.
    """
    return (
        panel_width
        - _PANEL_BORDER
        - _PANEL_BODY_PADDING
        - _OPTION_LIST_PADDING
        - _VERTICAL_SCROLLBAR
        - _CONTEXT_INDENT
    )


def wrap_lines(text: str, width: int) -> str:
    """Pre-wraps *text* on `\\n` every *width* columns.

    The `\\n` is what guarantees the indent: `hierarchical_item` indents
    every logical line, and only those — the automatic wrapping Textual
    does on a single over-wide line happens at render time and there is no
    way to indent it (see the docstring of `hierarchical_item`). Collapses
    whitespace before wrapping so that a description with breaks of its
    own does not blow up the grammar of one line per role.
    """
    if not text:
        return ""
    flattened = " ".join(text.split())
    return "\n".join(textwrap.wrap(flattened, width=width) or [""])


def _indented_field(text: str, style: str) -> Content:
    """Builds a field (disambiguation or context) with the indent on EVERY
    line, not just on the first.

    A field can arrive here with line breaks already embedded — for
    example `connections.py` pre-wraps a long description into two logical
    lines before calling `hierarchical_item`. If the indent were applied
    only once, in front of the whole block (as a single `Content.assemble`
    would do), the second line onwards would end up aligned to column 0 —
    the SAME column as the identity of the next entry. The indent is the
    cue for "this belongs to the entry above"; losing it on a continuation
    is the defect that motivated this whole phase, just on a smaller scale.

    Each line becomes its own `Content.assemble(_INDENT, (line, style))`
    — the indent as its own span, not whitespace added to the field's text
    by the caller — and the lines are joined with `Content("\n").join(...)`,
    which preserves the spans of each one. No extra whitespace enters
    `.plain` beyond the indent itself; `.plain` remains equal to the text
    the caller passed, only with the indent before each line.
    """
    parts = [
        Content.assemble(_INDENT, (line, style))
        for line in text.split("\n")
    ]
    return Content("\n").join(parts)


def hierarchical_item(
    identity: str,
    disambiguation: str = "",
    context: str = "",
) -> Content:
    """Builds a list item with up to three lines of visual hierarchy.

    Returns `Content`, not `str`: it is what `OptionList.add_option` and
    `DataTable` accept without falling back to plain Rich, which raises
    `MarkupError` on seeing a `$name` token (the same problem documented in
    `group_result.py._status_cell`). Each field is a styled span via
    `Content.assemble`, not parsed markup — the user's text reaches the
    final `Content` byte for byte, with no escaping and no risk of closing
    a tag.

    If `disambiguation` or `context` carry a `\n` (a caller that pre-wraps
    long text into several logical lines), EVERY line gets the indent —
    see `_indented_field`. This does NOT cover the automatic wrapping
    Textual itself does when a single line (without `\n`) is wider than
    the widget: that wrap is done at render time, after this `Content` has
    already been assembled, and Textual offers no way to give persistent
    indentation to the continuation of such a line. Whoever wants a
    guaranteed indent on a very long line must pre-break it on `\n` before
    calling this function — and that is what `wrap_lines` does, at the
    width `wrap_width` derives (which already subtracts the indent that
    every line of the field comes to pay). The Conexoes and Consultas
    lists do this; that is why the panels of both have a fixed width in
    the CSS.
    """
    line = Content.assemble((identity, "bold $ds-text-strong"))
    if disambiguation:
        line = line + "\n" + _indented_field(disambiguation, "$ds-text-muted")
    if context:
        line = line + "\n" + _indented_field(context, "$ds-text-disabled")
    return line


class NamedOption(Option):
    """`Option` that carries the item's name as DATA, not as an `id`.

    Name is dbqm's lookup key (`find_query`/`find_group`), so the
    temptation is to pass it as `Option(content, id=name)` and read it back
    from `event.option.id`. But `OptionList.add_option` raises
    `DuplicateID` on a repeated id: two queries with the same name in a
    hand-edited `queries.json` (the UI's creation flows block duplicates, a
    legacy file or one edited in an editor does not) made the WHOLE SCREEN
    fail to mount. Ambiguous data stays ambiguous — there is no way to make
    the selection unambiguous, and it is not the list's job to try; what it
    must do is NOT BREAK: paint both rows and resolve the selection by name
    exactly as it did before, letting the ambiguity show up in the search
    result, not in a dead screen.

    Keeping the name in an attribute of its own takes the `id` out of the
    picture entirely: there is no id to collide, and `name` stays "" when
    the data has an empty name, instead of turning into `None` and
    producing a silently dead row.
    """

    def __init__(self, content: Content, name: str) -> None:
        super().__init__(content)
        self.name = name
