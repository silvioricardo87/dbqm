"""Teste 2 do design system: paridade de tokens entre temas.

Sem ele, um tema fica com cor herdada errada e ninguem percebe ate alguem
reclamar. E a regra do guia: nenhuma cor pode ter definicao unica num tema.
"""
import re
from pathlib import Path

from dbqm.design.tokens import (
    SURFACES,
    THEMES,
    LIGHT_TOKENS,
    DARK_TOKENS,
    VALID_OVER,
)


def test_themes_declare_exactly_the_same_keys():
    assert set(DARK_TOKENS) == set(LIGHT_TOKENS)


def test_every_registered_theme_has_the_same_keys():
    esperado = set(DARK_TOKENS)
    for nome, tokens in THEMES.items():
        assert set(tokens) == esperado, f"tema {nome} diverge"


def test_every_token_has_an_explicit_hex_value():
    """`auto 60%` nao e calculavel a partir do arquivo; hex e."""
    for nome, tokens in THEMES.items():
        for chave, valor in tokens.items():
            assert valor.startswith("#") and len(valor) == 7, f"{nome}.{chave}={valor}"


def test_every_declared_surface_exists_as_a_token():
    for tema, tokens in THEMES.items():
        for s in SURFACES:
            assert s in tokens, f"tema {tema} nao define a superficie {s}"


def test_every_text_token_declares_which_backgrounds_it_is_valid_over():
    for token in VALID_OVER:
        assert token in DARK_TOKENS, f"{token} declarado em VALID_OVER nao existe"
        assert VALID_OVER[token], f"{token} nao declara nenhum fundo valido"


# --------------------------------------------------------------------------
# Teste 6 (do design system): toda variavel `$x` usada em DEFAULT_CSS existe.
#
# Sem ele, uma referencia a uma variavel que ninguem mais define nao quebra
# nada visivelmente: o Textual so cai para o proprio valor calculado embutido
# (ex.: `$border`), e a tela renderiza uma cor completamente diferente da
# pretendida sem erro nenhum. Foi exatamente isso que aconteceu na Task 2:
# `theme.py` parou de gravar a chave customizada "border" no dict de
# variaveis, e as 5 referencias a `$border` que sobraram em
# action_bar.py/panel.py/templates_sidebar.py passaram a resolver para o
# `border` embutido do Textual (derivado da paleta, nao de nenhum token) em
# vez do token `borda` que era a intencao.
#
# O guarda casa qualquer atribuicao (de modulo ou de classe) de uma string
# triple-quoted a um identificador, nao so `DEFAULT_CSS` literal. Antes so
# `DEFAULT_CSS = """..."""` era varrido; `dbqm/ui/theme.py::INERT_STATES_CSS`
# escapava por ter outro nome, e uma renomeacao de token la dentro deixaria
# `$ds-text-disabled`/`$ds-text-muted` resolvendo em silencio para um builtin
# do Textual — a mesma falha de `$border` que este guarda existe para pegar.

UI_ROOT = Path(__file__).resolve().parents[2] / "dbqm" / "ui"

_DEFAULT_CSS_BLOCK = re.compile(
    r'[A-Za-z_][A-Za-z0-9_]*\s*=\s*"""(.*?)"""', re.DOTALL
)
_CSS_VARIABLE = re.compile(r'\$([a-zA-Z][a-zA-Z0-9_-]*)')

# Campos nomeados do Theme que `dbqm/ui/theme.py::_build_theme` preenche a
# partir de um token (accent=identidade, background=fundo, ...), mais
# `text-muted`, variavel computada pelo proprio Textual a partir do
# foreground e que nunca teve — nem precisa ter — um token dedicado.
# Qualquer outro nome (border, panel-active, text-bright, text-dim, ...) e
# resquicio do tema antigo e nao deve aparecer em CSS novo.
DOCUMENTED_BUILTINS = frozenset({
    "primary", "secondary", "accent", "warning", "error", "success",
    "foreground", "background", "surface", "panel", "text-muted",
})


def _css_variables_used() -> set[str]:
    achadas: set[str] = set()
    for arquivo in sorted(UI_ROOT.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for bloco in _DEFAULT_CSS_BLOCK.findall(texto):
            for m in _CSS_VARIABLE.finditer(bloco):
                achadas.add(m.group(1))
    return achadas


def test_every_css_variable_is_a_token_or_a_documented_builtin():
    permitidas = set(DARK_TOKENS) | DOCUMENTED_BUILTINS
    usadas = _css_variables_used()
    desconhecidas = usadas - permitidas
    assert not desconhecidas, (
        f"DEFAULT_CSS referencia variavel(is) que nao sao token nem builtin "
        f"documentado: {sorted(desconhecidas)}"
    )
