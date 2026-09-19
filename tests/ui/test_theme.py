"""Tests for theme system."""
from dbqm.ui.theme import get_theme


def test_dark_theme_has_the_required_variables():
    theme = get_theme("plano-escuro")
    assert theme.name == "plano-escuro"
    assert theme.primary is not None
    assert theme.background is not None


def test_light_theme_has_the_required_variables():
    theme = get_theme("plano-claro")
    assert theme.name == "plano-claro"
    assert theme.primary is not None
    assert theme.background is not None


def test_get_theme_returns_dark_by_default():
    theme = get_theme("plano-escuro")
    assert theme.name == "plano-escuro"


def test_get_theme_returns_light():
    theme = get_theme("plano-claro")
    assert theme.name == "plano-claro"


def test_light_defines_accent_and_panel():
    """Check the wiring (theme.py -> tokens.py), never the value of the hex.

    A test comparing against a literal hex fails every time the palette is
    repainted (design system Task 8 is proof of that on its own) and does not
    catch the real bug: if `_build_theme` stopped mapping
    `background=tokens["ds-background"]`, a hex kept in sync by hand in the
    test would make the assertion pass with the wiring broken. Comparing
    against LIGHT_TOKENS proves the link, not the memory of which palette is
    active.
    """
    from dbqm.design.tokens import LIGHT_TOKENS

    light = get_theme("plano-claro")
    assert light.variables["ds-identity"] == LIGHT_TOKENS["ds-identity"]
    assert light.panel == LIGHT_TOKENS["ds-panel"]
    assert light.surface == LIGHT_TOKENS["ds-surface"]
    assert light.background == LIGHT_TOKENS["ds-background"]


def test_theme_exposes_every_token_as_a_css_variable():
    """Os componentes so podem consumir a camada semantica se ela chegar la."""
    from dbqm.design.tokens import DARK_TOKENS

    variables = get_theme("plano-escuro").variables
    for key in DARK_TOKENS:
        assert key in variables, f'token {key} never reaches the CSS'


def test_legacy_theme_names_still_work():
    """settings.json de quem ja usa o dbqm guarda github-dark/github-light."""
    assert get_theme("github-dark").name == "plano-escuro"
    assert get_theme("github-light").name == "plano-claro"


def test_unknown_theme_falls_back_to_dark():
    assert get_theme("inexistente").name == "plano-escuro"
