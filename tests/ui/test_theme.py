"""Tests for theme system."""
from dbqm.ui.theme import GITHUB_DARK, GITHUB_LIGHT, get_theme


def test_github_dark_has_required_vars():
    theme = GITHUB_DARK
    assert theme.name == "github-dark"
    assert theme.primary is not None
    assert theme.background is not None


def test_github_light_has_required_vars():
    theme = GITHUB_LIGHT
    assert theme.name == "github-light"
    assert theme.primary is not None
    assert theme.background is not None


def test_get_theme_returns_dark_by_default():
    theme = get_theme("github-dark")
    assert theme.name == "github-dark"


def test_get_theme_returns_light():
    theme = get_theme("github-light")
    assert theme.name == "github-light"


def test_get_theme_unknown_falls_back_to_dark():
    theme = get_theme("nonexistent")
    assert theme.name == "github-dark"


def test_dark_palette_matches_prototype():
    assert GITHUB_DARK.background == "#0d1117"
    assert GITHUB_DARK.surface == "#090b10"          # darker than panel
    assert GITHUB_DARK.panel == "#161b22"
    assert GITHUB_DARK.variables["accent"] == "#bc8cff"
    assert GITHUB_DARK.variables["panel-active"] == "#21262d"
    assert GITHUB_DARK.warning == "#d29922"


def test_light_defines_accent_and_panel():
    assert GITHUB_LIGHT.variables["accent"] == "#8250df"
    assert GITHUB_LIGHT.panel == "#ffffff"
    assert GITHUB_LIGHT.surface == "#ebedf0"
    assert GITHUB_LIGHT.background == "#f6f8fa"
