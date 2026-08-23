"""Teste 3 do design system: contraste calculado a partir dos tokens.

KNOWN_DEBT e uma lista auto-limpante: o teste exige igualdade exata com
as falhas reais. Uma falha nova reprova, e uma divida quitada tambem reprova,
forcando a remocao da linha. Assim ela nao apodrece.
"""
import pytest

from dbqm.design.tokens import (
    INTERFACE_FLOOR,
    TEXT_FLOOR,
    THEMES,
    INTERFACE_TOKENS,
    VALID_OVER,
)
from tests.design._contraste import ratio

# Quitada na Task 8: paleta Plano zera a divida herdada do tema GitHub.
KNOWN_DEBT: set[tuple[str, str, str]] = set()


def _failures() -> set[tuple[str, str, str]]:
    fora = set()
    for tema, tokens in THEMES.items():
        for token, fundos in VALID_OVER.items():
            piso = INTERFACE_FLOOR if token in INTERFACE_TOKENS else TEXT_FLOOR
            for fundo in fundos:
                if ratio(tokens[token], tokens[fundo]) < piso:
                    fora.add((tema, token, fundo))
    return fora


def test_contrast_matches_the_declared_debt_exactly():
    falhas = _failures()
    novas = falhas - KNOWN_DEBT
    quitadas = KNOWN_DEBT - falhas
    assert not novas, f"contraste novo abaixo do piso: {sorted(novas)}"
    assert not quitadas, (
        f"divida quitada — remova de KNOWN_DEBT: {sorted(quitadas)}"
    )


@pytest.mark.parametrize("tema", sorted(THEMES))
def test_body_text_passes_over_every_surface(tema):
    """O par mais usado do produto nao pode estar na lista de divida."""
    tokens = THEMES[tema]
    for fundo in VALID_OVER["ds-text"]:
        assert ratio(tokens["ds-text"], tokens[fundo]) >= TEXT_FLOOR
