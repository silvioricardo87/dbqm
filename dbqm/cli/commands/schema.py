"""Commands for seeing a database's shape: objects, describe, rows."""
from __future__ import annotations

import argparse
import sys
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
    sys.exit(int(exit_for(code)))


def _with_open_connection(args: argparse.Namespace, command: str, conn, acao):
    """Open a handle, run `acao(db)` on it, and map each failure to its token.

    The two failures are kept apart deliberately. `open_connection` failing
    means the database did not answer -> `connection_failed` (3). `acao`
    failing means the database answered and rejected what we asked -> a
    statement error (4), or `usage` (2) when `core/` says the capability does
    not exist on this engine at all. Collapsing both into `connection_failed`
    is what `run` and `sql` do, and it is the distinction `errors.py` exists
    to preserve: a caller retrying a connection failure would retry forever
    against a query the engine will never accept.
    """
    try:
        with deps.open_connection(conn) as db:
            # These two handlers exhaust everything `acao` can raise, so the
            # outer handler below can only ever see a failure from opening the
            # connection itself. That is what keeps the two apart.
            try:
                return acao(db)
            except deps.UnsupportedEngine as e:
                _fail_or_print(args, command, "usage", str(e))
            except Exception as e:
                _fail_or_print(args, command, "sql_error", str(e))
    except Exception as e:
        _fail_or_print(args, command, "connection_failed", str(e))


def cmd_objects(args: argparse.Namespace) -> None:
    """List database objects of one type."""
    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "objects", "not_found",
                       f"Conexao '{args.connection}' nao encontrada.")

    obj_type = args.type.upper()
    nomes = _with_open_connection(
        args, "objects", conn,
        lambda db: deps.list_objects(db, conn.db_type, obj_type),
    )

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


def cmd_describe(args: argparse.Namespace) -> None:
    """Show one object's shape: columns, keys and indexes.

    Dispatches on what the object turns out to be rather than asking the user
    to say table or view. No row count in either format: a COUNT(*) is a full
    scan, which is why `psql \\d` does not show one either. `-f table` and
    `-f json` carry the same content -- one shape for the command, not two.
    """
    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "describe", "not_found",
                       f"Conexao '{args.connection}' nao encontrada.")

    def acao(db):
        estrutura = deps.get_table_structure(db, conn.db_type, args.object)
        view = deps.get_view_definition(db, conn.db_type, args.object)
        return estrutura, view

    estrutura, view = _with_open_connection(args, "describe", conn, acao)

    definicao = view.sql_definition or ""
    if not estrutura.columns and not definicao:
        _fail_or_print(args, "describe", "not_found",
                       f"Objeto '{args.object}' nao encontrado em {conn.name}.")

    data = estrutura.to_dict()
    data["connection_name"] = conn.name
    if definicao:
        data["sql_definition"] = definicao

    if args.format == "json":
        ok("describe", data)
        return

    rotulo = "VIEW" if definicao else "TABLE"
    console.print(f"{escape(estrutura.table)} ({rotulo})")

    colunas = Table(show_header=True)
    colunas.add_column("Coluna")
    colunas.add_column("Tipo")
    colunas.add_column("Nulo")
    colunas.add_column("Chave")
    for c in estrutura.columns:
        chave = "PK" if c.is_pk else (f"-> {c.fk_ref}" if c.fk_ref else "")
        colunas.add_row(escape(c.name), escape(c.data_type),
                        "SIM" if c.nullable else "NAO", escape(chave))
    console.print(colunas)

    if estrutura.indexes:
        console.print("\nINDICES")
        for i in estrutura.indexes:
            marca = "UNIQUE " if i.is_unique else ""
            console.print(f"  {escape(i.name)}  {marca}({', '.join(i.columns)})")

    if definicao:
        console.print("\nDEFINICAO")
        console.print(definicao, markup=False, highlight=False)
