"""Teste 3 do design system: contraste calculado a partir dos tokens.

DIVIDA_CONHECIDA e uma lista auto-limpante: o teste exige igualdade exata com
as falhas reais. Uma falha nova reprova, e uma divida quitada tambem reprova,
forcando a remocao da linha. Assim ela nao apodrece.
"""
import pytest

from dbqm.design.tokens import (
    PISO_INTERFACE,
    PISO_TEXTO,
    TEMAS,
    TOKENS_DE_INTERFACE,
    VALIDO_SOBRE,
)
from tests.design._contraste import razao

# Quitada na Task 8: paleta Plano zera a divida herdada do tema GitHub.
DIVIDA_CONHECIDA: set[tuple[str, str, str]] = set()


def _falhas() -> set[tuple[str, str, str]]:
    fora = set()
    for tema, tokens in TEMAS.items():
        for token, fundos in VALIDO_SOBRE.items():
            piso = PISO_INTERFACE if token in TOKENS_DE_INTERFACE else PISO_TEXTO
            for fundo in fundos:
                if razao(tokens[token], tokens[fundo]) < piso:
                    fora.add((tema, token, fundo))
    return fora


def test_contraste_bate_exatamente_com_a_divida_declarada():
    falhas = _falhas()
    novas = falhas - DIVIDA_CONHECIDA
    quitadas = DIVIDA_CONHECIDA - falhas
    assert not novas, f"contraste novo abaixo do piso: {sorted(novas)}"
    assert not quitadas, (
        f"divida quitada — remova de DIVIDA_CONHECIDA: {sorted(quitadas)}"
    )


@pytest.mark.parametrize("tema", sorted(TEMAS))
def test_texto_principal_passa_sobre_toda_superficie(tema):
    """O par mais usado do produto nao pode estar na lista de divida."""
    tokens = TEMAS[tema]
    for fundo in VALIDO_SOBRE["texto"]:
        assert razao(tokens["texto"], tokens[fundo]) >= PISO_TEXTO
