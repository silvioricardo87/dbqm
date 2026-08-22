"""Teste 1 do design system: cor literal fora de token.

O guia chama este de o teste de maior retorno. Ele roda com um teto que so
desce: cada tarefa da migracao baixa TETO, e a Task 13 o zera. Assim ele ja
protege contra crescimento antes de a divida acabar.
"""
from tests.design._varredura import violacoes

# Baixar a cada tarefa da migracao. Task 13 fecha em 0.
TETO = 177


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
