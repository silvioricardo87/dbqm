"""Teste 2 do design system: paridade de tokens entre temas.

Sem ele, um tema fica com cor herdada errada e ninguem percebe ate alguem
reclamar. E a regra do guia: nenhuma cor pode ter definicao unica num tema.
"""
import re
from pathlib import Path

from dbqm.design.tokens import (
    SUPERFICIES,
    TEMAS,
    TOKENS_CLARO,
    TOKENS_ESCURO,
    VALIDO_SOBRE,
)


def test_temas_declaram_exatamente_as_mesmas_chaves():
    assert set(TOKENS_ESCURO) == set(TOKENS_CLARO)


def test_todo_tema_registrado_tem_as_mesmas_chaves():
    esperado = set(TOKENS_ESCURO)
    for nome, tokens in TEMAS.items():
        assert set(tokens) == esperado, f"tema {nome} diverge"


def test_todo_token_tem_valor_hexadecimal_explicito():
    """`auto 60%` nao e calculavel a partir do arquivo; hex e."""
    for nome, tokens in TEMAS.items():
        for chave, valor in tokens.items():
            assert valor.startswith("#") and len(valor) == 7, f"{nome}.{chave}={valor}"


def test_toda_superficie_declarada_existe_como_token():
    for tema, tokens in TEMAS.items():
        for s in SUPERFICIES:
            assert s in tokens, f"tema {tema} nao define a superficie {s}"


def test_todo_token_de_texto_declara_sobre_quais_fundos_e_valido():
    for token in VALIDO_SOBRE:
        assert token in TOKENS_ESCURO, f"{token} declarado em VALIDO_SOBRE nao existe"
        assert VALIDO_SOBRE[token], f"{token} nao declara nenhum fundo valido"


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

RAIZ_UI = Path(__file__).resolve().parents[2] / "dbqm" / "ui"

_BLOCO_DEFAULT_CSS = re.compile(r'DEFAULT_CSS\s*=\s*"""(.*?)"""', re.DOTALL)
_VARIAVEL_CSS = re.compile(r'\$([a-zA-Z][a-zA-Z0-9_-]*)')

# Campos nomeados do Theme que `dbqm/ui/theme.py::_construir` preenche a
# partir de um token (accent=identidade, background=fundo, ...), mais
# `text-muted`, variavel computada pelo proprio Textual a partir do
# foreground e que nunca teve — nem precisa ter — um token dedicado.
# Qualquer outro nome (border, panel-active, text-bright, text-dim, ...) e
# resquicio do tema antigo e nao deve aparecer em CSS novo.
BUILTINS_DOCUMENTADOS = frozenset({
    "primary", "secondary", "accent", "warning", "error", "success",
    "background", "surface", "panel", "text-muted",
})


def _variaveis_css_usadas() -> set[str]:
    achadas: set[str] = set()
    for arquivo in sorted(RAIZ_UI.rglob("*.py")):
        texto = arquivo.read_text(encoding="utf-8")
        for bloco in _BLOCO_DEFAULT_CSS.findall(texto):
            for m in _VARIAVEL_CSS.finditer(bloco):
                achadas.add(m.group(1))
    return achadas


def test_toda_variavel_css_e_token_ou_builtin_documentado():
    permitidas = set(TOKENS_ESCURO) | BUILTINS_DOCUMENTADOS
    usadas = _variaveis_css_usadas()
    desconhecidas = usadas - permitidas
    assert not desconhecidas, (
        f"DEFAULT_CSS referencia variavel(is) que nao sao token nem builtin "
        f"documentado: {sorted(desconhecidas)}"
    )
