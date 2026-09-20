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
    """The body of `def name(` up to the next top-level (or same-indent) def.

    The indent group is `[ \\t]*`, not `\\s*` -- `\\s` also matches `\\n`,
    so a blank line (or several) right before the `def` was captured as
    part of "the indent", which then had to match at the start of some
    later line to end the body. A blank line before the next sibling `def`
    broke that match and the extraction ran past its own function into
    whatever followed -- exactly what `test_the_guard_does_not_over_capture`
    below proves against the old pattern.
    """
    m = re.search(rf"^([ \t]*)def {re.escape(name)}\(", text, re.M)
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


def test_each_extraction_is_bounded_to_its_own_function():
    """For every pair, the CLI body carries no second `def cmd_` and the
    tool body carries no second `@server.tool(` -- if either extraction had
    bled into its neighbour, `test_each_tool_and_its_command_call_the_same_ops_function`
    could pass while comparing the wrong function's text."""
    server = SERVER.read_text(encoding="utf-8")
    overrun = []
    for tool, (module, command, _call) in PAIRS.items():
        tool_src = _function_source(server, {"list": "list_saved"}.get(tool, tool))
        cli_src = _function_source((COMMANDS / module).read_text(encoding="utf-8"), command)
        if "def cmd_" in cli_src:
            overrun.append((tool, "cli", cli_src))
        if "@server.tool(" in tool_src:
            overrun.append((tool, "server", tool_src))
    assert not overrun, [o[:2] for o in overrun]


def test_a_blank_line_before_the_matched_def_does_not_bleed_into_the_body():
    """The regression this guards: `^(\\s*)def` treats `\\s` as matching a
    newline too, so a blank line above the MATCHED def (`cmd_rows`, which
    the real source always has one above) is captured as part of "the
    indent" -- `indent` becomes `"\\n    "`, not `"    "`. The boundary
    search then requires that same blank-line-plus-indent shape to appear
    again, so a sibling with no blank line above it (`cmd_next`, reformatted
    onto the line right after `cmd_rows`'s body) does not end the capture;
    the search runs on and the extraction swallows `cmd_next` whole.

    Proven both ways on the same synthetic text: the old pattern
    over-captures `cmd_next` into `cmd_rows`'s body, the fixed one
    (`[ \\t]*`, which cannot absorb the blank line) does not.
    """
    text = (
        "class X:\n"
        "\n"
        "    def cmd_rows():\n"
        "        return 1\n"
        "    def cmd_next():\n"
        "        return 2\n"
        "\n"
        "    def cmd_last():\n"
        "        return 3\n"
    )

    old_pattern = re.compile(r"^(\s*)def cmd_rows\(", re.M)
    m = old_pattern.search(text)
    assert m
    old_indent = m.group(1)
    assert "\n" in old_indent, "the setup must reproduce the polluted indent"
    old_rest = text[m.end():]
    old_end = re.search(rf"^{old_indent}(?:def |@|return server)", old_rest, re.M)
    old_body = old_rest[: old_end.start()] if old_end else old_rest
    assert "def cmd_next" in old_body, "the old pattern was expected to over-capture"

    assert "def cmd_next" not in _function_source(text, "cmd_rows")
