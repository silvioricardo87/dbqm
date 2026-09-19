"""Commands for seeing a database's shape: objects, describe, rows."""
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.i18n import t
from dbqm.cli import deps, render
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
            except deps.ObjectNotFound as e:
                _fail_or_print(args, command, "not_found", str(e))
            except ValueError as e:
                # `_validate_identifier` refused the name before any
                # statement ran: bad input, not a statement the driver
                # rejected. Must come before the generic `Exception` arm
                # below or Python's first-match rule sends it to sql_error.
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
                       t("connection.not_found_named", name=args.connection))

    obj_type = args.type.upper()
    nomes = _with_open_connection(
        args, "objects", conn,
        lambda db: deps.list_objects(db, conn.db_type, obj_type),
    )

    if args.format == "json":
        ok("objects", {"connection_name": conn.name, "obj_type": obj_type,
                       "objects": nomes})
        return

    tabela = Table(title=t("objects.list_title", type=obj_type, connection=conn.name))
    tabela.add_column(t("common.name"))
    for nome in nomes:
        tabela.add_row(escape(nome))
    console.print(tabela)
    console.print(t("objects.count", count=len(nomes)))


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
                       t("connection.not_found_named", name=args.connection))

    def acao(db):
        estrutura = deps.get_table_structure(db, conn.db_type, args.object)
        view = deps.get_view_definition(db, conn.db_type, args.object)
        return estrutura, view

    estrutura, view = _with_open_connection(args, "describe", conn, acao)

    definicao = view.sql_definition or ""
    # `owner`, not the definition, is what says the object is a view. A view
    # whose source the connected user may not read comes back with its owner
    # set and an empty definition -- measured on SQL Server, where a missing
    # VIEW DEFINITION grant makes both information_schema.views and
    # sys.sql_modules return NULL rather than an error. Labelling on the
    # definition alone reports such a view as a table.
    e_view = bool(view.owner or definicao)
    if not estrutura.columns and not e_view:
        # "nao encontrado" would be a claim dbqm cannot make: a package or a
        # routine of that name may well exist. All this call establishes is
        # that it is not a table and not a view.
        _fail_or_print(args, "describe", "not_found",
                       t("describe.not_table_nor_view", name=args.object, connection=conn.name))

    tipo = "VIEW" if e_view else "TABLE"
    data = estrutura.to_dict()
    data["connection_name"] = conn.name
    # Stated rather than left to be inferred from which keys are present: a
    # consumer must not have to guess the object's type from the absence of
    # `sql_definition`, which is exactly what the unreadable-source case
    # would make it get wrong.
    data["object_type"] = tipo
    if definicao:
        data["sql_definition"] = definicao

    if args.format == "json":
        ok("describe", data)
        return

    console.print(f"{escape(estrutura.table)} ({tipo})")

    colunas = Table(show_header=True)
    colunas.add_column(t("common.column"))
    colunas.add_column(t("common.type"))
    colunas.add_column(t("common.nullable"))
    colunas.add_column(t("common.key"))
    for c in estrutura.columns:
        chave = "PK" if c.is_pk else (f"-> {c.fk_ref}" if c.fk_ref else "")
        colunas.add_row(escape(c.name), escape(c.data_type),
                        t("common.yes_short") if c.nullable else t("common.no_short"), escape(chave))
    console.print(colunas)

    if estrutura.indexes:
        console.print("\n" + t("describe.indexes_header"))
        for i in estrutura.indexes:
            marca = "UNIQUE " if i.is_unique else ""
            console.print(f"  {escape(i.name)}  {marca}({', '.join(i.columns)})")

    if definicao:
        console.print("\n" + t("describe.definition_header"))
        console.print(definicao, markup=False, highlight=False)


def cmd_rows(args: argparse.Namespace) -> None:
    """Browse a table's rows, paged.

    No `--where`: `dbqm sql` already takes a predicate, and a filter
    expression here would be injection surface bought for nothing.
    """
    if args.limit < 1:
        _fail_or_print(args, "rows", "usage", t("rows.limit_positive"))
    if args.offset < 0:
        _fail_or_print(args, "rows", "usage", t("rows.offset_not_negative"))

    conn = deps.find_connection(args.connection)
    if not conn:
        _fail_or_print(args, "rows", "not_found",
                       t("connection.not_found_named", name=args.connection))

    def acao(db):
        try:
            return deps.browse_table(
                db, conn.db_type, args.table, conn.name,
                limit=args.limit, offset=args.offset,
            )
        except ValueError:
            # `_validate_identifier` refused the name. Bad input, not a
            # missing table -- do not go asking whether it exists.
            raise
        except Exception as original:
            # Ask only now: on success this costs nothing, and the catalogue
            # answers authoritatively instead of us matching four dialects of
            # "table does not exist". Views are not tables, so a valid view
            # name would wrongly 404 without also checking "VIEW".
            try:
                tabelas = {t.upper() for t in deps.list_objects(db, conn.db_type, "TABLE")}
                vistas = {v.upper() for v in deps.list_objects(db, conn.db_type, "VIEW")}
            except Exception:
                # The diagnosis itself failed. Raise the ORIGINAL by name, not
                # a bare `raise`, which inside a nested handler re-raises the
                # inner one -- the user must learn what their own query did
                # wrong, not what the existence check did wrong.
                raise original from None
            if args.table.upper() not in tabelas | vistas:
                raise deps.ObjectNotFound(
                    t("rows.table_not_found", name=args.table, connection=conn.name)
                ) from original
            raise

    resultado = _with_open_connection(args, "rows", conn, acao)

    if args.format == "json":
        ok("rows", resultado.to_dict())
        return

    render._print_query_result(
        deps.QueryResult(
            query_name=resultado.table,
            connection_name=conn.name,
            columns=resultado.columns,
            rows=resultado.rows,
            row_count=resultado.row_count,
            elapsed=resultado.elapsed,
        ),
        args.format,
    )

    # `QueryResult` has no `total_count`, so the renderer cannot say it: a
    # human would see 100 rows of sixteen million and nothing to suggest there
    # is a second page. The JSON payload carries `total_count`; this is the
    # same fact for the reader. Only for `table` -- `csv` and `raw` are text
    # pipes, and a trailing sentence in them is corruption, not information.
    vistas = resultado.offset + resultado.row_count
    if args.format == "table" and resultado.total_count > vistas:
        console.print(
            t("rows.showing_page", seen=vistas, total=resultado.total_count)
        )
