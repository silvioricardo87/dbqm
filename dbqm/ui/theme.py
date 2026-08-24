"""Textual themes, built from dbqm/design/tokens.py, plus the global CSS for
inert states (INERT_STATES_CSS) that consumes them.

No color is written here: this module only translates the semantic tokens into
the format Textual expects. Changing the palette means changing tokens.py.

INERT_STATES_CSS lives here, not in dbqm/ui/app.py, because DBQMApp and
ThemedTestApp (tests/ui/_helpers.py) are siblings — both extend
textual.app.App directly, with no kinship between them — so a constant defined
only in DBQMApp would never reach the screen tests that mount ThemedTestApp.
Both import it from here.
"""
from __future__ import annotations

from textual.theme import Theme

from dbqm.design.tokens import THEMES

# Names recorded in settings.json before the design system.
LEGACY_NAMES: dict[str, str] = {
    "github-dark": "plano-escuro",
    "github-light": "plano-claro",
}

DEFAULT_THEME = "plano-escuro"

# Distinct inert states (Task 12): a disabled control is an action that is
# unavailable right now — the reason has to be reachable, never just the
# color; read-only is content to consume, not a broken form. The two rules
# use different tokens (text-disabled vs text-muted) and the second one also
# strips the control's border/background, so that the two never end up looking
# alike — the defect this task exists to prevent.
#
# It lives here (not in app.py) and is consumed both by `DBQMApp.DEFAULT_CSS`
# and by `tests/ui/_helpers.py::ThemedTestApp.DEFAULT_CSS`: the two Apps have
# no kinship between them (siblings, both straight from `textual.app.App`),
# and only `DEFAULT_CSS` combines along the MRO without erasing what an ad-hoc
# test subclass declares on its own — `CSS` (a single attribute, with no
# merge) would erase that.
INERT_STATES_CSS = """
*:disabled { color: $ds-text-disabled; }
.-read-only { color: $ds-text-muted; border: none; background: $ds-panel; }
"""


def _build_theme(name: str, tokens: dict[str, str], dark: bool) -> Theme:
    """Translates the semantic tokens into a Textual Theme.

    Every token becomes a CSS variable, including the ones that also feed a
    named Theme field: the components always reference `$token`, and the named
    fields exist only for Textual's built-in widgets.

    The named fields (`warning`, `error`, `success`) are on the OPERATION
    axis, never on the VERDICT axis — they paint toast/notify and other
    Textual-native widgets that have no notion of "these two pieces of data
    differ", only of "this action failed/succeeded/is a warning". Feeding them
    with `verdict-*` paints chrome and notifications with the color of a
    comparison result, and unlocks the documented rollback lever: reverting
    `verdict-match` to green would paint every success notification green,
    exactly the surface the design says must be left colorless. That is why
    `success` and `warning` map to `text-muted` (success with no ink, an
    informative warning with no ink) and only `error` uses an operation token
    (`op-failure`).
    """
    return Theme(
        name=name,
        primary=tokens["ds-identity"],
        secondary=tokens["ds-text-muted"],
        accent=tokens["ds-identity"],
        warning=tokens["ds-text-muted"],
        error=tokens["ds-op-failure"],
        success=tokens["ds-text-muted"],
        foreground=tokens["ds-text"],
        background=tokens["ds-background"],
        surface=tokens["ds-surface"],
        panel=tokens["ds-panel"],
        dark=dark,
        variables=dict(tokens),
    )


TEXTUAL_THEMES: dict[str, Theme] = {
    "plano-escuro": _build_theme("plano-escuro", THEMES["plano-escuro"], dark=True),
    "plano-claro": _build_theme("plano-claro", THEMES["plano-claro"], dark=False),
}


def get_theme(name: str) -> Theme:
    """Returns a theme by name, accepting the legacy names and falling back to
    the default."""
    name_ = LEGACY_NAMES.get(name, name)
    return TEXTUAL_THEMES.get(name_, TEXTUAL_THEMES[DEFAULT_THEME])
