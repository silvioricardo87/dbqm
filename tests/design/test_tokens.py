"""Teste 2 do design system: paridade de tokens entre temas.

Sem ele, um tema fica com cor herdada errada e ninguem percebe ate alguem
reclamar. E a regra do guia: nenhuma cor pode ter definicao unica num tema.
"""
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
