"""What `dbqm/ops/` may and may not do, read from its source.

Three rules, each the reason the layer exists: it raises only tokens the
CLI's exit-code table knows (a token invented here would be a KeyError in
`exit_for` at the worst possible moment); it imports nothing from a front
end (the MCP server and the CLI both sit above it); and it never paints or
exits (under the MCP's stdio transport, stdout is the protocol channel).
"""
from __future__ import annotations

import ast
from pathlib import Path

from dbqm.cli.errors import ERROR_CODES

OPS = Path(__file__).resolve().parents[2] / "dbqm" / "ops"
FRONT_ENDS = ("dbqm.cli", "dbqm.ui", "dbqm.mcp")


def _modules() -> list[Path]:
    return sorted(OPS.rglob("*.py"))


def test_every_token_raised_is_one_the_exit_table_knows():
    unknown = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "OperationError" and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value not in ERROR_CODES):
                unknown.append((path.name, node.lineno, node.args[0].value))
    assert not unknown, unknown


def test_ops_imports_no_front_end():
    offenders = []
    for path in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                # Both the module itself (`from dbqm.cli import errors`) and
                # each alias qualified onto it (`from dbqm import cli` ->
                # `dbqm.cli`) -- the second form has no `node.module` that
                # alone names the front end, only the alias does.
                names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
            for name in names:
                if any(name == fe or name.startswith(fe + ".") for fe in FRONT_ENDS):
                    offenders.append((path.name, node.lineno, name))
    assert not offenders, offenders


def test_ops_never_paints_or_exits():
    offenders = []
    for path in _modules():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if "print(" in line or "console" in line or "sys.exit" in line:
                offenders.append((path.name, lineno, line.strip()))
    assert not offenders, offenders
