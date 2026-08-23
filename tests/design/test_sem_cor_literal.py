"""Teste 1 do design system: cor literal fora de token.

O guia chama este de o teste de maior retorno. Ele roda com um teto que so
desce: cada tarefa da migracao baixa TETO. Assim ele ja protege contra
crescimento antes de a divida acabar. A Task 7 (relatorio HTML) zerou o teto.
"""
from tests.design._varredura import violations

# Zerado na Task 7: o relatorio HTML era a ultima fonte de cor literal.
TETO = 0


def test_literal_color_does_not_grow():
    """Com TETO = 0, "nao cresce" (`<=`) e "esta ajustado ao real" (`==`)
    colapsam na mesma comparacao — nao ha mais folga abaixo de zero para os
    dois virarem testes distintos. Ficou um so, com a mensagem que nomeia
    os arquivos ofensores."""
    achados = violations()
    assert len(achados) == TETO, (
        f"{len(achados)} cores literais, teto {TETO}. Novas:\n"
        + "\n".join(f"  {a}:{l}  {t}" for a, l, t in achados[:20])
    )
