"""Every Rich markup tag in the `dbqm/cli/` package must point at a real style.

The sibling of this test on the TUI side is `tests/ui/_helpers.py::ThemedTestApp`:
there, an orphan `$token` (e.g. `$border` with no match in the theme dict)
brings the widget mount down, so a test that mounts real widgets already
catches the typo. Rich has no such mechanism — a tag like `[op-falha]` (hyphen
instead of dot) raises an exception nowhere, neither in `Console.print` nor in
`Text.from_markup`: the unknown name is silently resolved to "no style" and the
text comes out with no color, no error, no log. Verified directly:

    >>> Console(file=..., force_terminal=True).print("[not.a.real.style]x[/]")
    'x\n'   # no exception, no ANSI sequence

That is: no test that merely *runs* a CLI command catches this typo — the whole
of `tests/test_cli.py` included, which runs the commands and checks the output,
would pass identically with `[op-falha]` in place of `[ds.op.failure]`. This test
exists to be the only one that catches it, and it has to cover BOTH forms in
which Rich accepts a style name, not just one:

  1. markup tag between brackets: `[ds.op.failure]texto[/]`
  2. the `style=` kwarg of any call (`console.print(..., style=...)`,
     `Table(..., style=...)`, `add_column(..., style=...)`, `Text(..., style=...)`)

The first round of this test only covered (1) — `style="ds-op-failure"` passed by
kwarg would have survived inspection by that round, because the tag regex only
looks inside `[...]`. A `style=` value is a loose string, with no bracket at
all.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from rich.style import Style

from dbqm.cli import rich_theme

CLI_DIR = Path(__file__).resolve().parents[1] / "dbqm" / "cli"
# Every module of the package, so a command group added later is covered
# the day it lands. `cli.py` became this package in 2.0.0; a path pinned
# to one file went stale the moment it was split.
CLI_PATHS = sorted(CLI_DIR.rglob("*.py"))

# A valid tag only contains identifier-words (letters/digits/./-), possibly
# several of them separated by spaces (e.g. "bold red"). That is what
# distinguishes a markup tag from a Python list/slice bracket, which almost
# always carries parentheses, commas, braces or quotes.
_TAG = re.compile(r"\[/?([A-Za-z][\w.\-]*(?:\s+[A-Za-z][\w.\-]*)*)\]")

# Structural Rich modifiers that are not style names on their own.
_MODIFIERS = {"on", "not"}


def _markup_names_in(path: Path) -> set[str]:
    """Every style name that cli.py references, via a `[...]` tag or via `style=`.

    Walks the AST (not the raw text) for two reasons:

    - Literal parts of an f-string stay isolated from the interpolated
      `{...}`, so a progress bracket like `f"[{atual}/{total}]"` never becomes
      a false tag: the AST breaks that literal into pieces around `{atual}`
      and `{total}`, and no isolated piece contains a closed `[...]`.
    - `style=` only exists as a call kwarg (`ast.Call`); walking the call
      nodes and looking at `keywords` catches `console.print(..., style=...)`,
      `Table(..., style=...)`, `add_column(..., style=...)`, `Text(...,
      style=...)` — any call, with no need to list each one.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for body in _TAG.findall(node.value):
                for word in body.split():
                    names.add(word)
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg != "style":
                    continue
                value = kw.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    for word in value.value.split():
                        names.add(word)

    return names


def test_every_cli_markup_name_resolves_in_the_theme_or_is_native_to_rich():
    styles = rich_theme().styles
    native = set(Style.STYLE_ATTRIBUTES) | _MODIFIERS

    unknown = sorted(
        name
        for path in CLI_PATHS
        for name in _markup_names_in(path)
        if name not in styles and name not in native
    )
    assert not unknown, (
        f"tag/kwarg de estilo em dbqm/cli/ referencia estilo inexistente: {unknown}"
    )
