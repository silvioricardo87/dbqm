"""Every MCP tool and its CLI command call the same ops function.

Read from the source, not from behaviour: behaviour tests prove the two
agree today, this proves nobody can add logic to one side only without
the pairing showing it. `server.py` uses the CLI's own aliases for the ops
modules so the text `alias.function(` means the same thing in both files.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "dbqm"
SERVER = ROOT / "mcp" / "server.py"
COMMANDS = ROOT / "cli" / "commands"

#: tool name -> (CLI module, CLI function, the ops call both must contain)
PAIRS = {
    "list": ("inspect.py", "cmd_list", "catalogue.connection_summary("),
    "test_connection": ("inspect.py", "cmd_test", "catalogue.test_connections("),
    "objects": ("schema.py", "cmd_objects", "ops_schema.list_objects("),
    "describe": ("schema.py", "cmd_describe", "ops_schema.describe("),
    "rows": ("schema.py", "cmd_rows", "ops_schema.rows("),
    "ddl": ("inspect.py", "cmd_ddl", "ops_schema.extract_ddl("),
    "history": ("inspect.py", "cmd_history", "catalogue.history("),
    "run": ("query.py", "cmd_run", "queries.run_query("),
    "run_group": ("query.py", "cmd_run_group", "compare.run_group("),
    "multi": ("query.py", "cmd_multi", "compare.multi("),
    "sql": ("query.py", "cmd_sql", "ops_sql.run_sql("),
}


def _function_source(text: str, name: str) -> str:
    """The body of `def name(` up to the next top-level (or same-indent) def."""
    m = re.search(rf"^(\s*)def {re.escape(name)}\(", text, re.M)
    assert m, name
    indent = m.group(1)
    rest = text[m.end():]
    end = re.search(rf"^{indent}(?:def |@|return server)", rest, re.M)
    return rest[: end.start()] if end else rest


def test_the_server_registers_exactly_the_paired_tools():
    text = SERVER.read_text(encoding="utf-8")
    registered = re.findall(r'@server\.tool\(name="([a-z_]+)"', text)
    assert sorted(registered) == sorted(PAIRS)


def test_each_tool_and_its_command_call_the_same_ops_function():
    server = SERVER.read_text(encoding="utf-8")
    missing = []
    for tool, (module, command, call) in PAIRS.items():
        tool_src = _function_source(server, {"list": "list_saved"}.get(tool, tool))
        cli_src = _function_source((COMMANDS / module).read_text(encoding="utf-8"), command)
        if call not in tool_src:
            missing.append((tool, "server", call))
        if call not in cli_src:
            missing.append((tool, f"{module}:{command}", call))
    assert not missing, missing


def test_the_guard_reads_real_functions():
    """`_function_source` must fail loudly on a name that is not there,
    or a renamed command would make the pairing test pass on nothing."""
    import pytest
    with pytest.raises(AssertionError):
        _function_source("def other():\n    pass\n", "cmd_rows")
