"""Commands for managing saved connections: add, update, rm, show, list."""
from __future__ import annotations

import argparse
import json
import sys

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.commands.inspect import cmd_list
from dbqm.cli.params import resolve_password
from dbqm.cli.render import console

# Set by `build_parser` (in `dbqm.cli`) so `cmd_connection` can print the
# group's own help (add/update/rm/show/list) on a bare `dbqm connection`
# instead of a one-line reminder. Simplest way to reach a subparser created
# deep inside that function without threading it through `COMMAND_MAP`/`args`.
_connection_parser: argparse.ArgumentParser | None = None


_CONNECTION_OUTCOME_TEXT = {
    "created": "criada",
    "updated": "atualizada",
    "removed": "removida",
}


def _print_connection_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        print(json.dumps({"name": name, outcome: True}, ensure_ascii=False))
        return
    console.print(f'Conexao "{escape(name)}" {_CONNECTION_OUTCOME_TEXT[outcome]}.')


def _connection_values(args: argparse.Namespace, password: str | None) -> dict:
    """Only the flags actually given. A flag left out must not overwrite.

    `None` means "not mentioned on this command line" — dropped here so that
    `build` sees an absent key, which for the password is what means "keep the
    stored one".
    """
    values = {
        "name": args.name,
        "db_type": args.db_type,
        "mode": args.mode,
        "host": args.host,
        "port": args.port,
        "service_name": args.service_name,
        "database": args.database,
        "tns_path": args.tns_path,
        "tns_name": args.tns_name,
        "user": args.user,
        "description": args.description,
        "password": password,
    }
    return {key: value for key, value in values.items() if value is not None}


def _exit_with_errors(errors: list[str]) -> None:
    for error in errors:
        console.print(f"[ds.op.failure]{escape(error)}[/ds.op.failure]")
    sys.exit(2)


def _connection_add(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import save_connections

    if deps.find_connection(args.name) is not None:
        console.print(f'[ds.op.failure]Conexao "{escape(args.name)}" ja existe.[/ds.op.failure]')
        sys.exit(2)

    # Validate everything but the password first: a terminal user should
    # learn about a bad --type before being asked to type a secret that
    # turns out not to matter.
    values = _connection_values(args, None)
    errors = validate(values)
    if errors:
        _exit_with_errors(errors)

    if args.no_password:
        password = ""
    else:
        password = resolve_password(
            args, "DBQM_PASSWORD", "Senha da conexao: ", required=True
        )
    values["password"] = password

    conn = build(values)

    if args.test_before_save:
        ok, msg = deps.test_connection(conn)
        if not ok:
            console.print(f"[ds.op.failure]{msg}[/ds.op.failure]")
            console.print("[dim]Conexao nao gravada.[/dim]")
            sys.exit(3)

    connections = deps.load_connections()
    connections.append(conn)
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "created")


def _connection_update(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import save_connections

    existing = deps.find_connection(args.name)
    if existing is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    if args.no_password:
        password = ""  # an explicit empty value clears the stored password
    else:
        # use_env=False: an ambient DBQM_PASSWORD is not something the user
        # said on THIS command line, and update's contract is that what you
        # did not pass does not change. --password-stdin or --no-password
        # are the only ways to change the stored password here.
        password = resolve_password(
            args, "DBQM_PASSWORD", "Senha da conexao: ", required=False,
            use_env=False,
        )

    # Start from what is stored and lay the given flags on top: on a command
    # line, what was not said was not changed. `created_at` and the stored
    # password are dropped from the base because `build` reads them from
    # `existing` — re-encrypting the ciphertext would double-wrap it.
    merged = existing.to_dict()
    merged.pop("password", None)
    merged.pop("created_at", None)
    merged.update(_connection_values(args, password))

    errors = validate(merged)
    if errors:
        _exit_with_errors(errors)

    conn = build(merged, existing)

    if args.test_before_save:
        ok, msg = deps.test_connection(conn)
        if not ok:
            console.print(f"[ds.op.failure]{msg}[/ds.op.failure]")
            console.print("[dim]Conexao nao alterada.[/dim]")
            sys.exit(3)

    connections = deps.load_connections()
    index = next(i for i, c in enumerate(connections) if c.name == conn.name)
    connections[index] = conn
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "updated")


def _connection_show(args: argparse.Namespace) -> None:
    conn = deps.find_connection(args.name)
    if conn is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    data = conn.to_dict()
    # Never the ciphertext: the Fernet key lives next to the config, so
    # printing it puts a decryptable password into whatever captured stdout.
    data["password"] = "***" if conn.password else ""

    if args.format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    table = Table(title=f"Conexao: {escape(conn.name)}")
    table.add_column("Campo")
    table.add_column("Valor")
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _connection_rm(args: argparse.Namespace) -> None:
    from dbqm.models.connection import delete_connection

    if deps.find_connection(args.name) is None:
        console.print(
            f'[ds.op.failure]Conexao "{escape(args.name)}" nao encontrada.[/ds.op.failure]'
        )
        sys.exit(2)

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            console.print(
                "[ds.op.failure]Use --yes para remover sem confirmacao."
                "[/ds.op.failure]"
            )
            sys.exit(2)
        resposta = input(f'Remover a conexao "{args.name}"? [s/N] ').strip().lower()
        if resposta not in ("s", "sim"):
            if args.format == "json":
                print(json.dumps({"name": args.name, "removed": False}, ensure_ascii=False))
            else:
                console.print("Cancelado.")
            return

    delete_connection(args.name)
    _print_connection_outcome(args.format, args.name, "removed")


def _connection_list(args: argparse.Namespace) -> None:
    """The same listing as `dbqm list connections`.

    Three lines of delegation so that `dbqm connection --help` shows a whole
    CRUD; without it, whoever reads that help cannot find the listing verb.
    """
    cmd_list(argparse.Namespace(resource="connections", format=args.format))


_CONNECTION_SUBCOMMANDS = {
    "add": _connection_add,
    "update": _connection_update,
    "rm": _connection_rm,
    "show": _connection_show,
    "list": _connection_list,
}


def cmd_connection(args: argparse.Namespace) -> None:
    """Manage saved connections."""
    handler = _CONNECTION_SUBCOMMANDS.get(getattr(args, "subcommand", None))
    if handler is None:
        # A bare `dbqm connection` prints the group's own help (add/update/
        # rm/show/list, with their flags) rather than a one-line reminder.
        if _connection_parser is not None:
            _connection_parser.print_help()
        else:
            console.print(
                "[ds.op.failure]Use: dbqm connection add|update|rm|show|list"
                "[/ds.op.failure]"
            )
        sys.exit(2)
    handler(args)
