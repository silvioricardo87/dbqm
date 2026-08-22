"""Toda tag de markup do Rich em cli.py precisa apontar para um estilo real.

O irmao deste teste do lado da TUI e `tests/ui/_helpers.py::ThemedTestApp`: la,
um `$token` orfao (ex.: `$border` sem correspondente no dict de tema) derruba
a montagem do widget, entao um teste que monta widgets de verdade ja pega o
typo. O Rich nao tem esse mecanismo — uma tag como `[op-falha]` (hifen em vez
de ponto) nao levanta excecao em lugar nenhum, nem em `Console.print`, nem em
`Text.from_markup`: o nome desconhecido e resolvido silenciosamente para
"sem estilo" e o texto sai sem cor, sem erro, sem log. Verificado direto:

    >>> Console(file=..., force_terminal=True).print("[not.a.real.style]x[/]")
    'x\n'   # sem excecao, sem sequencia ANSI

Ou seja: nenhum teste que apenas *executa* um comando do CLI pega esse typo —
inclusive `tests/test_cli.py` inteiro, que roda os comandos e confere saida,
passaria identico com `[op-falha]` no lugar de `[op.falha]`. Este teste existe
para ser o unico que pega: ele nao renderiza nada, so verifica estaticamente
que todo nome usado dentro de uma tag `[...]` do cli.py e uma chave real do
tema (`tema_rich().styles`) ou um atributo/abreviacao nativo do Rich
(`Style.STYLE_ATTRIBUTES` — bold/b, dim/d, italic/i, etc.) ou um dos
modificadores estruturais `on`/`not`.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from rich.style import Style

from dbqm.cli import tema_rich

CLI_PATH = Path(__file__).resolve().parents[1] / "dbqm" / "cli.py"

# Uma tag valida so contem palavras-identificador (letras/digitos/./-),
# possivelmente varias separadas por espaco (ex.: "bold red"). Isso e o que
# distingue uma tag de markup de um colchete de lista/slice do Python, que
# quase sempre carrega parenteses, virgulas, chaves ou aspas.
_TAG = re.compile(r"\[/?([A-Za-z][\w.\-]*(?:\s+[A-Za-z][\w.\-]*)*)\]")

# Modificadores estruturais do Rich que nao sao nomes de estilo por si so.
_MODIFICADORES = {"on", "not"}


def _nomes_de_markup_em(caminho: Path) -> set[str]:
    """Todo nome referenciado dentro de uma tag `[...]` em literais de string.

    Anda pela AST (nao pelo texto bruto) para que partes literais de f-string
    sejam vistas isoladas dos `{...}` interpolados — assim um colchete de
    progresso como `f"[{atual}/{total}]"` nunca vira uma tag falsa: a AST
    quebra esse literal em pedacos em volta do `{atual}` e do `{total}`, e
    nenhum dos pedacos isolados contem um `[...]` fechado.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()
    for node in ast.walk(arvore):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for corpo in _TAG.findall(node.value):
                for palavra in corpo.split():
                    nomes.add(palavra)
    return nomes


def test_todo_nome_de_markup_do_cli_resolve_no_tema_ou_e_nativo_do_rich():
    estilos = tema_rich().styles
    nativos = set(Style.STYLE_ATTRIBUTES) | _MODIFICADORES

    desconhecidos = sorted(
        nome for nome in _nomes_de_markup_em(CLI_PATH)
        if nome not in estilos and nome not in nativos
    )
    assert not desconhecidos, (
        f"tag de markup em cli.py referencia estilo inexistente: {desconhecidos}"
    )
