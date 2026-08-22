"""Varre o codigo por cor escrita a mao. Utilitario de teste.

Duas formas contam como cor literal:
  - hexadecimal (`#58a6ff`)
  - nome de cor no markup do Rich/Textual (`[green]`, `[bold red]`)

`[dim]`, `[b]`, `[i]` e afins NAO contam: sao atributos de estilo, nao cores.
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ_PACOTE = Path(__file__).resolve().parents[2] / "dbqm"

_HEX = re.compile(r"#[0-9a-fA-F]{6}\b")
_NOMES = (
    "red", "green", "yellow", "blue", "cyan", "magenta", "white", "black",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_cyan", "bright_magenta", "bright_white", "bright_black",
)
_MARKUP = re.compile(
    r"\[/?(?:(?:b|bold|i|italic|u|underline|dim)\s+)*(?:" + "|".join(_NOMES) + r")\]"
)

# Unico arquivo onde escrever cor e o trabalho.
ISENTOS = {"dbqm/design/tokens.py"}

Violacao = tuple[str, int, str]


def violacoes() -> list[Violacao]:
    """Toda cor literal fora dos arquivos isentos, com arquivo e linha."""
    achados: list[Violacao] = []
    for arquivo in sorted(RAIZ_PACOTE.rglob("*.py")):
        rel = arquivo.relative_to(RAIZ_PACOTE.parent).as_posix()
        if rel in ISENTOS:
            continue
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for padrao in (_HEX, _MARKUP):
                for m in padrao.finditer(linha):
                    achados.append((rel, numero, m.group(0)))
    return achados
