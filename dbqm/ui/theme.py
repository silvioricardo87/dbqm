"""Theme definitions for the Textual UI."""
from __future__ import annotations

from textual.theme import Theme

GITHUB_DARK = Theme(
    name="github-dark",
    primary="#58a6ff",
    secondary="#8b949e",
    warning="#e3b341",
    error="#f85149",
    success="#3fb950",
    background="#0d1117",
    surface="#161b22",
    panel="#161b22",
    dark=True,
    variables={
        "border": "#30363d",
        "text": "#c9d1d9",
        "text-bright": "#f0f6fc",
        "text-dim": "#484f58",
    },
)

GITHUB_LIGHT = Theme(
    name="github-light",
    primary="#0969da",
    secondary="#656d76",
    warning="#9a6700",
    error="#cf222e",
    success="#1a7f37",
    background="#ffffff",
    surface="#f6f8fa",
    panel="#f6f8fa",
    dark=False,
    variables={
        "border": "#d0d7de",
        "text": "#1f2328",
        "text-bright": "#000000",
        "text-dim": "#656d76",
    },
)

_THEMES: dict[str, Theme] = {
    "github-dark": GITHUB_DARK,
    "github-light": GITHUB_LIGHT,
}


def get_theme(name: str) -> Theme:
    """Return a theme by name, falling back to github-dark."""
    return _THEMES.get(name, GITHUB_DARK)
