"""Commands for seeing a database's shape: objects, describe, rows."""
from __future__ import annotations

import argparse
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console

OBJECT_TYPES = ["TABLE", "VIEW", "PACKAGE", "ROUTINE"]


def _fail_or_print(args: argparse.Namespace, command: str, code: str,
                   message: str) -> NoReturn:
    """Mirrors `connection._fail_or_print`: one branch point for `-f json`.

    Under json the envelope goes to stderr and stdout stays empty; otherwise
    the message prints for a human. Both exit with the same mapped code, so a
    script sees one number regardless of the format it asked for.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    raise SystemExit(int(exit_for(code)))


def cmd_objects(args: argparse.Namespace) -> None:
    """List database objects of one type."""
    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "objects", "not_found",
                       f"Conexao '{args.connection}' nao encontrada.")

    obj_type = args.type.upper()
    try:
        with deps.open_connection(conn) as db:
            try:
                nomes = deps.list_objects(db, conn.db_type, obj_type)
            except deps.UnsupportedEngine as e:
                _fail_or_print(args, "objects", "usage", str(e))
    except deps.UnsupportedEngine:
        raise
    except SystemExit:
        raise
    except Exception as e:
        _fail_or_print(args, "objects", "connection_failed", str(e))

    if args.format == "json":
        ok("objects", {"connection_name": conn.name, "obj_type": obj_type,
                       "objects": nomes})
        return

    tabela = Table(title=f"{obj_type} em {conn.name}")
    tabela.add_column("Nome")
    for nome in nomes:
        tabela.add_row(escape(nome))
    console.print(tabela)
    console.print(f"{len(nomes)} objeto(s).")
