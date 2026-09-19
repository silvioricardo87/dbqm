"""`dbqm describe-cli`: the CLI surface describing itself.

Ships instead of separate documentation, so an agent (or a script) can ask
what dbqm can do rather than trust a README that may have drifted. The only
way that promise holds is if the answer comes from the same
`argparse.ArgumentParser` the CLI already builds and dispatches through --
never a second, hand-typed list of command names living next to this one.

`build_parser` (in `dbqm.cli`) hands this module the subparsers action right
after creating it, the same trick `config_cmd._config_parser` and
`connection._connection_parser` use to reach a parser built deep inside that
function without importing `dbqm.cli` back into a module it already imports
from (a circular import).

Every command's `_actions` is read the same way argparse reads it to print
`--help`: nothing here is per-command logic, so a flag added to an existing
command, or an entire command added next year, appears without anyone
touching this file. Several commands hold a subparsers action of their own,
so the walk recurses: a command that itself has subcommands reports them
under `subcommands`, described the same way, arguments included, rather than
as a bare `choices` list that names a subcommand without saying how to call
it. No name -- of a command, a subcommand or a flag -- appears anywhere in
this module. That is the whole premise: a list written here is a list that
goes stale, and the parser already holds the truth.
"""
from __future__ import annotations

import argparse
import sys
from typing import Any

from rich.markup import escape
from rich.table import Table

from dbqm.i18n import t
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console

# Set by `build_parser` right after `parser.add_subparsers()` -- see module
# docstring. `None` only means `build_parser` has not run yet; `cmd_describe_cli`
# treats that as `unexpected` rather than silently reporting zero commands.
_subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser] | None = None


def _find_nested_subparsers(
    parser: argparse.ArgumentParser,
) -> argparse._SubParsersAction[argparse.ArgumentParser] | None:
    """The subparsers action `parser` itself added, if any.

    Several commands have one -- their subcommands live behind it. A leaf
    command like `sql` has none. Deliberately not listed by name: this module
    enumerates nothing about the surface, and a comment naming today's
    commands would go stale the way the code cannot.
    """
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _describe_argument(action: argparse.Action) -> dict[str, Any]:
    return {
        "flags": list(action.option_strings) or [action.dest],
        "required": bool(action.required),
        "choices": list(action.choices) if action.choices is not None else None,
        "help": action.help or "",
    }


def _describe_parser(name: str, help_text: str, parser: argparse.ArgumentParser) -> dict[str, Any]:
    """One command, or one subcommand, recursively.

    `-h`/`--help` is dropped by type (`isinstance`, not a `dest` string --
    a user argument that happened to land on `dest="help"` would still be
    reported). A nested subparsers action is left out of `arguments` and
    reported as `subcommands` instead, so a caller can tell "this name takes
    its own arguments" from "this name is itself a group of commands".
    """
    nested = _find_nested_subparsers(parser)
    arguments = [
        _describe_argument(action)
        for action in parser._actions
        if not isinstance(action, argparse._HelpAction) and action is not nested
    ]
    described: dict[str, Any] = {"name": name, "help": help_text, "arguments": arguments}
    if nested is not None:
        described["subcommands"] = _describe_children(nested)
    return described


def _describe_children(
    subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser],
) -> list[dict[str, Any]]:
    """Every child of one subparsers action, in the order the parser exposes them."""
    help_by_name = {
        choice_action.dest: choice_action.help or ""
        for choice_action in subparsers_action._choices_actions
    }
    return [
        _describe_parser(name, help_by_name.get(name, ""), parser)
        for name, parser in subparsers_action.choices.items()
    ]


def _print_command(cmd: dict[str, Any], depth: int = 0) -> None:
    indent = "  " * depth
    console.print(f"{indent}[ds.identity]{escape(str(cmd['name']))}[/]  {escape(str(cmd['help']))}")
    arguments = cmd["arguments"]
    if arguments:
        table = Table(show_header=True, box=None, padding=(0, 1, 0, 2))
        table.add_column(t("describe_cli.flags_column"))
        table.add_column(t("describe_cli.required_column"))
        table.add_column(t("describe_cli.choices_column"))
        table.add_column(t("common.description"))
        for arg in arguments:
            flags = ", ".join(arg["flags"])
            required = (t("common.yes_short_word") if arg["required"]
                        else t("common.no_short_word"))
            choices = ", ".join(str(c) for c in arg["choices"]) if arg["choices"] else "-"
            table.add_row(escape(flags), required, escape(choices), escape(arg["help"]))
        console.print(table)
    for sub in cmd.get("subcommands", []):
        _print_command(sub, depth=depth + 1)
    console.print()


def cmd_describe_cli(args: argparse.Namespace) -> None:
    """Describe every dbqm CLI command by walking the parser itself.

    `-f json` is the point: a machine-readable map of every command
    (recursing into `subcommands` where a command has its own), its help
    text, and every argument's flags/required/choices/help, read live from
    `build_parser()`. `-f table` prints the same walk as a readable summary.

    A parser that was never built (`_subparsers_action` still `None`) is
    `unexpected`, not an empty, successful list -- dbqm having no commands
    is never a true answer, so it is not one this reports.
    """
    if _subparsers_action is None:
        message = t("describe_cli.parser_missing")
        if args.format == "json":
            fail("describe-cli", "unexpected", message)
        console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
        sys.exit(int(exit_for("unexpected")))

    commands = _describe_children(_subparsers_action)

    if args.format == "json":
        ok("describe-cli", {"commands": commands})
        return

    for cmd in commands:
        _print_command(cmd)
