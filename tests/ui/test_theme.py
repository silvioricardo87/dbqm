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


def test_light_defines_accent_and_panel():
    """Confere a fiacao (theme.py -> tokens.py), nunca o valor do hex.

    Um teste que compara contra um hex literal reprova toda vez que a
    paleta e repintada (a propria Task 8 do design system e prova disso) e
    nao pega o bug real: se `_construir` parasse de mapear
    `background=tokens["fundo"]`, um hex sincronizado a mao no teste faria
    a asserção passar mesmo com a fiacao quebrada. Comparar contra
    TOKENS_CLARO prova a ligacao, nao a memoria de qual paleta esta ativa.
    """
    from dbqm.design.tokens import TOKENS_CLARO

    light = get_theme("plano-claro")
    assert light.variables["identidade"] == TOKENS_CLARO["identidade"]
    assert light.panel == TOKENS_CLARO["painel"]
    assert light.surface == TOKENS_CLARO["superficie"]
    assert light.background == TOKENS_CLARO["fundo"]


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
