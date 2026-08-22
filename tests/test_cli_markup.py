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
para ser o unico que pega, e precisa cobrir as DUAS formas que o Rich aceita
um nome de estilo, nao so uma:

  1. tag de markup entre colchetes: `[op.falha]texto[/]`
  2. o kwarg `style=` de qualquer chamada (`console.print(..., style=...)`,
     `Table(..., style=...)`, `add_column(..., style=...)`, `Text(..., style=...)`)

A primeira rodada deste teste so cobria (1) — `style="op-falha"` passado por
kwarg teria sobrevivido inspecionado por essa rodada, porque a regex de tag
so olha para dentro de `[...]`. Um valor de `style=` e uma string solta, sem
colchete nenhum.
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
    """Todo nome de estilo que cli.py referencia, via tag `[...]` ou via `style=`.

    Anda pela AST (nao pelo texto bruto) por dois motivos:

    - Partes literais de f-string ficam isoladas dos `{...}` interpolados,
      entao um colchete de progresso como `f"[{atual}/{total}]"` nunca vira
      uma tag falsa: a AST quebra esse literal em pedacos em volta do
      `{atual}` e do `{total}`, e nenhum pedaco isolado contem um `[...]`
      fechado.
    - `style=` so existe como kwarg de chamada (`ast.Call`); andar pelos nos
      de chamada e olhar `keywords` pega `console.print(..., style=...)`,
      `Table(..., style=...)`, `add_column(..., style=...)`, `Text(...,
      style=...)` — qualquer chamada, sem precisar listar cada uma.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    nomes: set[str] = set()

    for node in ast.walk(arvore):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for corpo in _TAG.findall(node.value):
                for palavra in corpo.split():
                    nomes.add(palavra)
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg != "style":
                    continue
                valor = kw.value
                if isinstance(valor, ast.Constant) and isinstance(valor.value, str):
                    for palavra in valor.value.split():
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
        f"tag/kwarg de estilo em cli.py referencia estilo inexistente: {desconhecidos}"
    )
