"""Tests for theme system."""
from dbqm.ui.theme import get_theme


def test_tema_escuro_tem_variaveis_obrigatorias():
    theme = get_theme("plano-escuro")
    assert theme.name == "plano-escuro"
    assert theme.primary is not None
    assert theme.background is not None


def test_tema_claro_tem_variaveis_obrigatorias():
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


def test_get_theme_unknown_falls_back_to_dark():
    theme = get_theme("nonexistent")
    assert theme.name == "plano-escuro"


def test_light_defines_accent_and_panel():
    light = get_theme("plano-claro")
    assert light.variables["identidade"] == "#e3b341"
    assert light.panel == "#ffffff"
    assert light.surface == "#ebedf0"
    assert light.background == "#f6f8fa"


def test_tema_expoe_todo_token_como_variavel_css():
    """Os componentes so podem consumir a camada semantica se ela chegar la."""
    from dbqm.design.tokens import TOKENS_ESCURO

    variaveis = get_theme("plano-escuro").variables
    for chave in TOKENS_ESCURO:
        assert chave in variaveis, f"token {chave} nao chega ao CSS"


def test_nomes_de_tema_antigos_continuam_funcionando():
    """settings.json de quem ja usa o dbqm guarda github-dark/github-light."""
    assert get_theme("github-dark").name == "plano-escuro"
    assert get_theme("github-light").name == "plano-claro"


def test_tema_desconhecido_cai_no_escuro():
    assert get_theme("inexistente").name == "plano-escuro"
