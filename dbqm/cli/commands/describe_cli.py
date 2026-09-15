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
touching this file.
"""
from __future__ import annotations

import argparse
from typing import Any

from dbqm.cli.envelope import ok
from dbqm.cli.render import console

# Set by `build_parser` right after `parser.add_subparsers()` -- see module
# docstring. `None` only in a test that imports this module without going
# through `build_parser` first.
_subparsers_action: argparse._SubParsersAction[argparse.ArgumentParser] | None = None

#: dest of the `-h`/`--help` action argparse adds to every parser on its own.
#: It is boilerplate, not part of the surface a command's author wrote, so it
#: is left out of the description.
_HELP_DEST = "help"


def _describe_argument(action: argparse.Action) -> dict[str, Any]:
    return {
        "flags": list(action.option_strings) or [action.dest],
        "required": bool(action.required),
        "choices": list(action.choices) if action.choices is not None else None,
        "help": action.help or "",
    }


def _describe_command(
    name: str, help_text: str, parser: argparse.ArgumentParser,
) -> dict[str, Any]:
    arguments = [
        _describe_argument(action)
        for action in parser._actions
        if action.dest != _HELP_DEST
    ]
    return {"name": name, "help": help_text, "arguments": arguments}


def _walk_commands() -> list[dict[str, Any]]:
    """Every top-level command, read straight from the live parser tree."""
    if _subparsers_action is None:
        return []
    help_by_name = {
        choice_action.dest: choice_action.help or ""
        for choice_action in _subparsers_action._choices_actions
    }
    return [
        _describe_command(name, help_by_name.get(name, ""), parser)
        for name, parser in _subparsers_action.choices.items()
    ]


def _print_table(commands: list[dict[str, Any]]) -> None:
    from rich.markup import escape
    from rich.table import Table

    for cmd in commands:
        console.print(f"[ds.identity]{escape(str(cmd['name']))}[/]  {escape(str(cmd['help']))}")
        arguments = cmd["arguments"]
        if arguments:
            table = Table(show_header=True, box=None, padding=(0, 1, 0, 2))
            table.add_column("Flags")
            table.add_column("Obrigatorio")
            table.add_column("Opcoes")
            table.add_column("Descricao")
            for arg in arguments:
                flags = ", ".join(arg["flags"])
                required = "sim" if arg["required"] else "nao"
                choices = ", ".join(str(c) for c in arg["choices"]) if arg["choices"] else "-"
                table.add_row(escape(flags), required, escape(choices), escape(arg["help"]))
            console.print(table)
        console.print()


def cmd_describe_cli(args: argparse.Namespace) -> None:
    """Describe every dbqm CLI command by walking the parser itself.

    `-f json` is the point: a machine-readable map of every command, its
    help text, and every argument's flags/required/choices/help, read live
    from `build_parser()`. `-f table` prints the same walk as a readable
    summary.
    """
    commands = _walk_commands()

    if args.format == "json":
        ok("describe-cli", {"commands": commands})
        return

    _print_table(commands)
