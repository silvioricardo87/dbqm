"""Teste 1 do design system: cor literal fora de token.

O guia chama este de o teste de maior retorno. Ele roda com um teto que so
desce: cada tarefa da migracao baixa TETO. Assim ele ja protege contra
crescimento antes de a divida acabar. A Task 7 (relatorio HTML) zerou o teto.
"""
from tests.design._varredura import violacoes

# Zerado na Task 7: o relatorio HTML era a ultima fonte de cor literal.
TETO = 0


def test_cor_literal_nao_cresce():
    achados = violacoes()
    assert len(achados) <= TETO, (
        f"{len(achados)} cores literais, teto {TETO}. Novas:\n"
        + "\n".join(f"  {a}:{l}  {t}" for a, l, t in achados[:20])
    )


def test_teto_esta_ajustado_ao_real():
    """Impede que o teto fique folgado e pare de proteger."""
    achados = violacoes()
    assert len(achados) == TETO, (
        f"divida caiu para {len(achados)} — baixe TETO para esse valor"
    )
