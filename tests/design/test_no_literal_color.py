"""Design system test 1: literal colour outside a token.

The guide calls this the highest-return test. It runs with a ceiling that
only goes down: every task of the migration lowers TETO. That way it already
protects against growth before the debt is paid off. Task 7 (the HTML report)
brought the ceiling to zero.
"""
from tests.design._scan import violations

# Brought to zero in Task 7: the HTML report was the last source of literal colour.
CEILING = 0


def test_literal_color_does_not_grow():
    """With TETO = 0, "does not grow" (`<=`) and "is tightened to the real
    figure" (`==`) collapse into the same comparison — there is no slack left
    below zero for the two to be distinct tests. Only one is left, with the
    message that names the offending files."""
    found = violations()
    assert len(found) == CEILING, (
        f"{len(found)} cores literais, teto {CEILING}. Novas:\n"
        + "\n".join(f"  {a}:{line}  {t}" for a, line, t in found[:20])
    )
