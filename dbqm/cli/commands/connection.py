"""Commands for managing saved connections: add, update, rm, show, list."""
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.commands.inspect import cmd_list
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
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

# `outcome` (past participle, used in the Rich sentence) to the verb the
# envelope's `command` field uses instead (`connection.add`, not
# `connection.created`).
_CONNECTION_OUTCOME_VERB = {
    "created": "add",
    "updated": "update",
    "removed": "rm",
}


def _print_connection_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        verbo = _CONNECTION_OUTCOME_VERB[outcome]
        ok(f"connection.{verbo}", {"name": name, outcome: True})
        return
    console.print(f'Conexao "{escape(name)}" {_CONNECTION_OUTCOME_TEXT[outcome]}.')


def _fail_or_print(
    args: argparse.Namespace,
    command: str,
    code: str,
    message: str,
    *,
    extra: str | None = None,
) -> NoReturn:
    """The one place this module branches between the envelope and Rich text.

    Under `-f json` this is `fail()` and nothing has reached stdout yet;
    under `table` it prints the same Rich failure message as always (plus an
    optional dim follow-up line) and exits with the exit code the same
    `code` token maps to, so the two branches never drift apart.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    if extra:
        console.print(extra)
    sys.exit(int(exit_for(code)))


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


def _exit_with_errors(args: argparse.Namespace, command: str, errors: list[str]) -> NoReturn:
    if args.format == "json":
        fail(command, "validation", "; ".join(errors))
    for error in errors:
        console.print(f"[ds.op.failure]{escape(error)}[/ds.op.failure]")
    sys.exit(2)


def _connection_add(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import save_connections

    if deps.find_connection(args.name) is not None:
        _fail_or_print(args, "connection.add", "usage",
                        f'Conexao "{args.name}" ja existe.')

    # Validate everything but the password first: a terminal user should
    # learn about a bad --type before being asked to type a secret that
    # turns out not to matter.
    values = _connection_values(args, None)
    errors = validate(values)
    if errors:
        _exit_with_errors(args, "connection.add", errors)

    if args.no_password:
        password = ""
    else:
        password = resolve_password(
            args, "DBQM_PASSWORD", "Senha da conexao: ", required=True
        )
    values["password"] = password

    conn = build(values)

    if args.test_before_save:
        succeeded, msg = deps.test_connection(conn)
        if not succeeded:
            _fail_or_print(args, "connection.add", "connection_failed", msg,
                            extra="[dim]Conexao nao gravada.[/dim]")

    connections = deps.load_connections()
    connections.append(conn)
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "created")


def _connection_update(args: argparse.Namespace) -> None:
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import save_connections

    existing = deps.find_connection(args.name)
    if existing is None:
        _fail_or_print(args, "connection.update", "not_found",
                        f'Conexao "{args.name}" nao encontrada.')

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
        _exit_with_errors(args, "connection.update", errors)

    conn = build(merged, existing)

    if args.test_before_save:
        succeeded, msg = deps.test_connection(conn)
        if not succeeded:
            _fail_or_print(args, "connection.update", "connection_failed", msg,
                            extra="[dim]Conexao nao alterada.[/dim]")

    connections = deps.load_connections()
    index = next(i for i, c in enumerate(connections) if c.name == conn.name)
    connections[index] = conn
    save_connections(connections)
    _print_connection_outcome(args.format, conn.name, "updated")


def _connection_show(args: argparse.Namespace) -> None:
    conn = deps.find_connection(args.name)
    if conn is None:
        _fail_or_print(args, "connection.show", "not_found",
                        f'Conexao "{args.name}" nao encontrada.')

    data = conn.to_dict()
    # Never the ciphertext: the Fernet key lives next to the config, so
    # printing it puts a decryptable password into whatever captured stdout.
    data["password"] = "***" if conn.password else ""

    if args.format == "json":
        ok("connection.show", data)
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
        _fail_or_print(args, "connection.rm", "not_found",
                        f'Conexao "{args.name}" nao encontrada.')

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, "connection.rm", "usage",
                            "Use --yes para remover sem confirmacao.")
        resposta = input(f'Remover a conexao "{args.name}"? [s/N] ').strip().lower()
        if resposta not in ("s", "sim"):
            if args.format == "json":
                ok("connection.rm", {"name": args.name, "removed": False})
            else:
                console.print("Cancelado.")
            return

    delete_connection(args.name)
    _print_connection_outcome(args.format, args.name, "removed")


def _connection_list(args: argparse.Namespace) -> None:
    """The same listing as `dbqm list connections`.

    The table branch still delegates to `cmd_list` so `dbqm connection
    --help` shows a whole CRUD; the json branch builds the envelope itself
    instead of delegating, because `cmd_list` is migrated separately in
    Task 6 and the two must not half-migrate each other.
    """
    if args.format == "json":
        items = deps.load_connections()
        data = [{"name": c.name, "db_type": c.db_type, "target": c.display_target()}
                 for c in items]
        ok("connection.list", data)
        return
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
