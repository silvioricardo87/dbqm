"""Shared infrastructure for UI tests.

`ThemedTestApp` exists so that the tests' ad-hoc harnesses (`class
XxxTestApp(App)` scattered across test_screens.py/test_modals.py/test_widgets.py)
mount the same themes the real DBQMApp registers in __init__ — without it,
any DEFAULT_CSS that uses a pure token (e.g. $ds-border, which unlike
$accent/$primary is not a built-in Textual variable) breaks the mounting of
the widget.

Deliberately NOT a global autouse fixture: an earlier version of this module
monkeypatched `App.__init__` for every test App, and that masked the very
regression that motivated this infrastructure — the test stayed green even
with the theme registration removed from DBQMApp, because the fixture
reapplied the registration from the outside. Each harness has to inherit from
ThemedTestApp explicitly, so that only the real DBQMApp proves that it
registers and activates the theme on its own.
"""
from __future__ import annotations

import re

from textual.app import App

from dbqm.ui.theme import INERT_STATES_CSS, DEFAULT_THEME, TEXTUAL_THEMES


class ThemedTestApp(App):
    """Base for a test App: registers and activates the design system themes."""

    # Mirrors `DBQMApp.DEFAULT_CSS` (Task 12): without it, an ad-hoc harness
    # that mounts `.-read-only`/`disabled=True` would not see the visual
    # distinction between the two — the same class of gap that motivated this
    # file for the themes.
    DEFAULT_CSS = INERT_STATES_CSS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for tema in TEXTUAL_THEMES.values():
            self.register_theme(tema)
        self.theme = DEFAULT_THEME


_STARS = "★☆ "


def rendered_names(option_list) -> list[str]:
    """The names of a query/group list as it PAINTS them.

    Reads the first line (the identity, in the grammar of
    `hierarchical_item`) of the `prompt` of each mounted option, without the
    favourite star. It exists because the obvious alternative — reading
    `Option.id` — measures an attribute and not what the person sees: the
    names stopped travelling in the `id` precisely because two items with the
    same name brought the whole screen down with `DuplicateID`, and a test
    that reads `id` would have stayed green while the list no longer mounted.
    """
    nomes = []
    for i in range(option_list.option_count):
        prompt = option_list.get_option_at_index(i).prompt
        texto = prompt.plain if hasattr(prompt, "plain") else str(prompt)
        linhas = texto.splitlines() or [""]
        nomes.append(linhas[0].lstrip(_STARS).rstrip())
    return nomes


_SVG_ESCAPES = {"&#160;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"'}


def rendered_text(app) -> str:
    """The text the screen REALLY paints, line by line.

    Reads the SVG from `App.export_screenshot()` — which only contains what
    fitted in the viewport — and returns the text of the `<text>` elements
    with the escaping undone. It exists because `widget.region` lies about
    visibility: the Oracle section of the Configuracoes screen had
    `region.height == 3` and still did not show up, clipped by an ancestor
    with `overflow: hidden`. A test that asserts `region.height > 0` passes
    with the defect present.

    The SVG's `\xa0` becomes an ordinary space so that searching for a phrase
    ("Client em uso") works the way the person reads it.
    """
    svg = app.export_screenshot()
    linhas = []
    for bruto in re.findall(r">([^<>]*)</text>", svg):
        texto = bruto
        for de, para in _SVG_ESCAPES.items():
            texto = texto.replace(de, para)
        linhas.append(texto.replace("\xa0", " "))
    return "\n".join(linhas)


def rendered_lines(app) -> list[str]:
    """The screen's lines as the compositor PAINTS them, with position.

    Complements `rendered_text`: that one finds a phrase, this one says what
    is at (x, y) — which is the only way to assert about the FRAME, which is
    not text. A panel's `Region.height` does not prove that its bottom line
    was drawn: `#er-select-phase` measured 24 in height on a 24-line screen
    starting at y=1, and the bottom border simply did not exist.
    """
    return [
        "".join(segmento.text for segmento in faixa)
        for faixa in app.screen._compositor.render_strips()
    ]


def crop(app, widget) -> list[str]:
    """The lines painted inside *widget*'s region."""
    linhas = rendered_lines(app)
    r = widget.region
    return [linha[r.x : r.x + r.width] for linha in linhas[r.y : r.y + r.height]]
