"""dbqm design tokens — layers 1 and 2 of the "Plano" design system.

This module is the lowest layer of the project: it imports nothing from `dbqm`.
Consumers: `ui/theme.py` (Textual), `cli.py` (Rich) and `core/html_report.py`
(CSS). This exists because `core/` cannot import `ui/`, and it was because of
that rule that the HTML report ended up inventing a palette of its own.

The Plano palette (Task 8) replaces the values inherited from the GitHub theme.
The keys do not change — only the values.
"""
from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------- layer 1
# Primitives ordered by luminance: a higher number is always darker.
# slate (dark):   950 #0b0e14 · 900 #0f131b · 850 #151a24 · 800 #1e2531
#                   700 #2b3342 · 500 #6b7688 · 450 #6b7a93 · 300 #9aa4b5
#                   100 #d5dae4 · 050 #f2f5fa
# snow (light):     000 #ffffff · 050 #f4f6f9 · 100 #f2f5f8 · 150 #eaeef3
#                   300 #d3dae3 · 500 #7b8798 · 600 #788291 · 700 #5b6577
#                   900 #1c2230 · 950 #0a0e16
# inks:    amber 400 #e3b341 / 800 #7d5600   (identity, SQL*Plus lineage)
#          persimmon 400 #ff8a5c / 800 #a83a0c   (disagrees)
#          indigo 400 #8b9bff / 800 #3f49c4   (absent)
#          crimson 400 #ff6b72 / 800 #c02434   (failure)

# ---------------------------------------------------------------- layer 2
# Semantic tokens: what the color MEANS. Components consume only these.
#
# The `ds-` prefix is not decoration: without it, seven of the fifteen names
# would collide with Textual BUILT-IN variables — `background`, `surface`,
# `panel`, `border`, `text`, `text-muted`, `text-disabled`. A collision there
# is not an error: `Theme.variables` OVERRIDES the builtin of the same name
# (`ColorSystem._generate` reads each one via `self.variables.get(name,
# default)`), so `$text-muted` would stop being the derived value that the
# native Textual widgets use and would become our token, changing painting
# outside dbqm with no warning whatsoever. And the code depends on this
# separation: `tests/design/test_tokens.py::DOCUMENTED_BUILTINS` exists
# precisely to tell "Textual builtin" apart from "our token" in the CSS.
DARK_TOKENS: Final[dict[str, str]] = {
    "ds-background": "#0b0e14",
    "ds-surface": "#0f131b",
    "ds-panel": "#151a24",
    "ds-surface-raised": "#1e2531",
    "ds-border": "#2b3342",
    "ds-border-strong": "#6b7a93",
    "ds-text": "#d5dae4",
    "ds-text-muted": "#9aa4b5",
    "ds-text-strong": "#f2f5fa",
    "ds-text-disabled": "#6b7688",
    "ds-identity": "#e3b341",
    # dbqm has no green: OK is the absence of ink. Reverting the bet is
    # swapping this single value.
    "ds-verdict-match": "#9aa4b5",
    "ds-verdict-diff": "#ff8a5c",
    "ds-verdict-absent": "#8b9bff",
    "ds-op-failure": "#ff6b72",
}

LIGHT_TOKENS: Final[dict[str, str]] = {
    "ds-background": "#f4f6f9",
    "ds-surface": "#eaeef3",
    "ds-panel": "#ffffff",
    "ds-surface-raised": "#f2f5f8",
    "ds-border": "#d3dae3",
    "ds-border-strong": "#7b8798",
    "ds-text": "#1c2230",
    "ds-text-muted": "#5b6577",
    "ds-text-strong": "#0a0e16",
    "ds-text-disabled": "#788291",
    "ds-identity": "#7d5600",
    "ds-verdict-match": "#5b6577",
    "ds-verdict-diff": "#a83a0c",
    "ds-verdict-absent": "#3f49c4",
    "ds-op-failure": "#c02434",
}

# `plano-escuro`/`plano-claro` are the only PORTUGUESE names that stay, and on
# purpose: they are not code identifiers, they are VALUES RECORDED in the
# `settings.json` of whoever already uses dbqm. `ui/theme.py::LEGACY_NAMES`
# already carries a migration map from `github-dark`/`github-light` to them;
# renaming them now would break the saved configuration a second time and would
# force a second migration layer. The token KEYS above are internal (only the
# code reads them) and that is why they were translated; these two names are
# not.
THEMES: Final[dict[str, dict[str, str]]] = {
    "plano-escuro": DARK_TOKENS,
    "plano-claro": LIGHT_TOKENS,
}

# Surfaces onto which text may be drawn.
SURFACES: Final[tuple[str, ...]] = (
    "ds-background", "ds-surface", "ds-panel", "ds-surface-raised",
)

# Pair rule (guide, section 3): each ink token declares which backgrounds it is
# valid over. None is valid over translucent fill — over translucent, use the
# text color of the surface underneath.
VALID_OVER: Final[dict[str, tuple[str, ...]]] = {
    "ds-text": SURFACES,
    "ds-text-muted": SURFACES,
    "ds-text-strong": SURFACES,
    "ds-text-disabled": SURFACES,
    "ds-border-strong": SURFACES,
    "ds-identity": SURFACES,
    "ds-op-failure": ("ds-panel", "ds-surface"),
    # "ds-background" is listed here because `core/html_report.py` draws `.ok`/`.diff`/
    # `.absent` straight onto `body { background: var(--ds-background) }` — the
    # most common pair in the report. Leaving it out was gratuitous narrowing:
    # the contrast test only computes declared pairs, so a real composed
    # pair (and the most frequent one in the report) stayed invisible
    # to the ratchet. All three pass in both variants, minimum 5.42:1.
    "ds-verdict-match": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
    "ds-verdict-diff": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
    "ds-verdict-absent": ("ds-panel", "ds-surface", "ds-surface-raised", "ds-background"),
}

# Tokens judged by the interface floor (3:1) instead of the text floor (4.5:1).
INTERFACE_TOKENS: Final[frozenset[str]] = frozenset(
    {"ds-text-disabled", "ds-border-strong"}
)

TEXT_FLOOR: Final[float] = 4.5
INTERFACE_FLOOR: Final[float] = 3.0
