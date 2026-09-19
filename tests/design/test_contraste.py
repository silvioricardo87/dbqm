"""Design system test 3: contrast computed from the tokens.

KNOWN_DEBT is a self-cleaning list: the test demands exact equality with
the real failures. A new failure fails, and a debt that has been paid off
fails too, forcing the line to be removed. That is how it does not rot.
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
    outside = set()
    for theme, tokens in THEMES.items():
        for token, backgrounds in VALID_OVER.items():
            floor = INTERFACE_FLOOR if token in INTERFACE_TOKENS else TEXT_FLOOR
            for deep_path in backgrounds:
                if ratio(tokens[token], tokens[deep_path]) < floor:
                    outside.add((theme, token, deep_path))
    return outside


def test_contrast_matches_the_declared_debt_exactly():
    failures = _failures()
    new_ones = failures - KNOWN_DEBT
    settled = KNOWN_DEBT - failures
    assert not new_ones, f"contraste novo abaixo do piso: {sorted(new_ones)}"
    assert not settled, (
        f"divida quitada — remova de KNOWN_DEBT: {sorted(settled)}"
    )


@pytest.mark.parametrize("theme", sorted(THEMES))
def test_body_text_passes_over_every_surface(theme):
    """The pair the product uses most cannot be on the debt list."""
    tokens = THEMES[theme]
    for deep_path in VALID_OVER["ds-text"]:
        assert ratio(tokens["ds-text"], tokens[deep_path]) >= TEXT_FLOOR
