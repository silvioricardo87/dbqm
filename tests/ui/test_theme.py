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
