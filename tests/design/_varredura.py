"""Varre o codigo por cor escrita a mao. Utilitario de teste.

Duas formas contam como cor literal:
  - hexadecimal (`#58a6ff`, `#abc`, `#12345678`)
  - nome de cor no markup do Rich/Textual (`[green]`, `[bold red]`, `[white on red]`)

`[dim]`, `[b]`, `[i]` e afins NAO contam: sao atributos de estilo, nao cores.

Limitacoes conhecidas (nao sao tratadas):
  - Nomes de cores estendidas do Rich (256-color, ex: `grey37`, `deep_pink4`, `color(124)`)
    Sao raros e enumerá-los causaria falsos positivos em markup ordinario.
"""
from __future__ import annotations

import re
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "dbqm"

# Hex em 3, 6 ou 8 digitos. Negative lookahead evita dupla contagem e rejeita
# seletores CSS como '#add-row', '#abc_panel' que nao sao cores.
# Cores literais nunca sao seguidas de letra, digito ou hifen; seletores CSS sim.
# Exemplo: em "#e3b #e3b341", pega "#e3b" e "#e3b341", nao "#e3b" dentro de "#e3b341".
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])")
_NAMES = (
    "red", "green", "yellow", "blue", "cyan", "magenta", "white", "black",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_cyan", "bright_magenta", "bright_white", "bright_black",
)
_MARKUP = re.compile(
    r"\[/?(?:(?:b|bold|i|italic|u|underline|dim|on)\s+)*(?:" + "|".join(_NAMES) + r")\]"
)

# Unico arquivo onde escrever cor e o trabalho.
EXEMPT = {"dbqm/design/tokens.py"}

Violation = tuple[str, int, str]


def violations() -> list[Violation]:
    """Toda cor literal fora dos arquivos isentos, com arquivo e linha."""
    achados: list[Violation] = []
    for arquivo in sorted(PACKAGE_ROOT.rglob("*.py")):
        rel = arquivo.relative_to(PACKAGE_ROOT.parent).as_posix()
        if rel in EXEMPT:
            continue
        for numero, linha in enumerate(
            arquivo.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for padrao in (_HEX, _MARKUP):
                for m in padrao.finditer(linha):
                    achados.append((rel, numero, m.group(0)))
    return achados
