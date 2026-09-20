"""What `dbqm/mcp/` may and may not do, read from its source.

Modeled on `tests/design/test_ops_policy.py`. The MCP server sits over
`ops/` exactly as the CLI does, so it must never reach into `dbqm.ui` (a
different front end) or `dbqm.cli`'s command layer (parsing and rendering
that belongs to the CLI alone) -- and under stdio it must never paint,
because stdout is the protocol channel a stray `print()` would corrupt.
"""
from __future__ import annotations

import ast
from pathlib import Path

MCP = Path(__file__).resolve().parents[2] / "dbqm" / "mcp"

#: Prefixes a `dbqm.*` import may resolve to. Anything else under `dbqm.` --
#: `dbqm.ui`, `dbqm.cli` bare, `dbqm.cli.commands` -- is refused.
ALLOWED_DBQM_PREFIXES = (
    "dbqm.ops",
    "dbqm.i18n",
    "dbqm.models",
    "dbqm._version",
    "dbqm.cli.errors",
    "dbqm.mcp",
)

#: Literal text that must never appear in `dbqm/mcp/**`, docstrings
#: included -- a docstring saying "stdout" as a plain word (`server.py`'s
#: own module docstring does) is fine; `sys.stdout` as a name is not.
FORBIDDEN_LITERALS = ("print(", "console", "sys.stdout")


def _modules() -> list[Path]:
    return sorted(MCP.rglob("*.py"))


def _import_names(tree: ast.AST) -> list[tuple[int, str]]:
    """(lineno, dotted name) for every import target -- the module itself
    and each alias qualified onto it, the same two forms
    `test_ops_policy.py::test_ops_imports_no_front_end` checks."""
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.append((node.lineno, a.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append((node.lineno, node.module))
            for a in node.names:
                names.append((node.lineno, f"{node.module}.{a.name}"))
    return names


def test_no_stdout_writes_anywhere_in_dbqm_mcp():
    offenders = []
    for path in _modules():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for literal in FORBIDDEN_LITERALS:
                if literal in line:
                    offenders.append((path.name, lineno, line.strip()))
    assert not offenders, offenders


def test_dbqm_mcp_imports_no_front_end_but_its_own():
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for lineno, name in _import_names(tree):
            if not name.startswith("dbqm."):
                continue  # third-party / stdlib -- not this guard's concern
            if name == "dbqm.cli" or name.startswith("dbqm.cli.commands"):
                offenders.append((path.name, lineno, name))
                continue
            if name == "dbqm.ui" or name.startswith("dbqm.ui."):
                offenders.append((path.name, lineno, name))
                continue
            if not any(name == p or name.startswith(p + ".") for p in ALLOWED_DBQM_PREFIXES):
                offenders.append((path.name, lineno, name))
    assert not offenders, offenders
