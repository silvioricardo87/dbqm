"""Temas do Textual, construidos a partir de dbqm/design/tokens.py.

Nenhuma cor e escrita aqui: este modulo so traduz os tokens semanticos para o
formato que o Textual espera. Trocar a paleta e trocar tokens.py.
"""
from __future__ import annotations

from textual.theme import Theme

from dbqm.design.tokens import TEMAS

# Nomes gravados em settings.json antes do design system.
NOMES_LEGADOS: dict[str, str] = {
    "github-dark": "plano-escuro",
    "github-light": "plano-claro",
}

PADRAO = "plano-escuro"


def _construir(nome: str, tokens: dict[str, str], escuro: bool) -> Theme:
    """Traduz os tokens semanticos para um Theme do Textual.

    Todo token vira variavel de CSS, inclusive os que tambem alimentam um
    campo nomeado do Theme: os componentes referenciam sempre `$token`, e os
    campos nomeados existem so para os widgets embutidos do Textual.
    """
    return Theme(
        name=nome,
        primary=tokens["identidade"],
        secondary=tokens["texto-apoio"],
        accent=tokens["identidade"],
        warning=tokens["veredito-difere"],
        error=tokens["op-falha"],
        success=tokens["veredito-igual"],
        foreground=tokens["texto"],
        background=tokens["fundo"],
        surface=tokens["superficie"],
        panel=tokens["painel"],
        dark=escuro,
        variables=dict(tokens),
    )


TEMAS_TEXTUAL: dict[str, Theme] = {
    "plano-escuro": _construir("plano-escuro", TEMAS["plano-escuro"], escuro=True),
    "plano-claro": _construir("plano-claro", TEMAS["plano-claro"], escuro=False),
}


def get_theme(name: str) -> Theme:
    """Devolve um tema pelo nome, aceitando os nomes antigos e caindo no padrao."""
    nome = NOMES_LEGADOS.get(name, name)
    return TEMAS_TEXTUAL.get(nome, TEMAS_TEXTUAL[PADRAO])
