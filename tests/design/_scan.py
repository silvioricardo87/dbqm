"""Scans the code for hand-written color. Test utility.

Two forms count as a literal color:
  - hexadecimal (`#58a6ff`, `#abc`, `#12345678`)
  - a color name in Rich/Textual markup (`[green]`, `[bold red]`, `[white on red]`)

`[dim]`, `[b]`, `[i]` and the like do NOT count: they are style attributes, not colors.

Known limitations (not handled):
  - Rich's extended color names (256-color, e.g. `grey37`, `deep_pink4`, `color(124)`)
    They are rare and enumerating them would cause false positives in ordinary markup.
"""
from __future__ import annotations

import re
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[2] / "dbqm"

# Hex in 3, 6 or 8 digits. The negative lookahead avoids double counting and
# rejects CSS selectors such as '#add-row', '#abc_panel' that are not colors.
# Literal colors are never followed by a letter, digit or hyphen; CSS selectors are.
# Example: in "#e3b #e3b341" it takes "#e3b" and "#e3b341", not "#e3b" inside "#e3b341".
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])")
_NAMES = (
    "red", "green", "yellow", "blue", "cyan", "magenta", "white", "black",
    "bright_red", "bright_green", "bright_yellow", "bright_blue",
    "bright_cyan", "bright_magenta", "bright_white", "bright_black",
)
_MARKUP = re.compile(
    r"\[/?(?:(?:b|bold|i|italic|u|underline|dim|on)\s+)*(?:" + "|".join(_NAMES) + r")\]"
)

# The only file where writing color is the job.
EXEMPT = {"dbqm/design/tokens.py"}

Violation = tuple[str, int, str]


def violations() -> list[Violation]:
    """Every literal color outside the exempt files, with file and line."""
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
