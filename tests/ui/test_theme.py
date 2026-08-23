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
    """Confere a fiacao (theme.py -> tokens.py), nunca o valor do hex.

    Um teste que compara contra um hex literal reprova toda vez que a
    paleta e repintada (a propria Task 8 do design system e prova disso) e
    nao pega o bug real: se `_build_theme` parasse de mapear
    `background=tokens["ds-background"]`, um hex sincronizado a mao no teste faria
    a asserção passar mesmo com a fiacao quebrada. Comparar contra
    LIGHT_TOKENS prova a ligacao, nao a memoria de qual paleta esta ativa.
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

    variaveis = get_theme("plano-escuro").variables
    for chave in DARK_TOKENS:
        assert chave in variaveis, f"token {chave} nao chega ao CSS"


def test_legacy_theme_names_still_work():
    """settings.json de quem ja usa o dbqm guarda github-dark/github-light."""
    assert get_theme("github-dark").name == "plano-escuro"
    assert get_theme("github-light").name == "plano-claro"


def test_unknown_theme_falls_back_to_dark():
    assert get_theme("inexistente").name == "plano-escuro"
