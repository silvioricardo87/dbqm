"""Commands for seeing a database's shape: objects, describe, rows."""
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.i18n import t
from dbqm.cli import render
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console
from dbqm.ops import catalogue, deps
from dbqm.ops import schema as ops_schema
from dbqm.ops.errors import OperationError

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


def cmd_objects(args: argparse.Namespace) -> None:
    """List database objects of one type."""
    try:
        conn = catalogue.connection(args.connection)
        names = ops_schema.list_objects(conn, args.type)
    except OperationError as e:
        _fail_or_print(args, "objects", e.code, e.message)

    obj_type = args.type.upper()

    if args.format == "json":
        ok("objects", {"connection_name": conn.name, "obj_type": obj_type,
                       "objects": names})
        return

    table = Table(title=t("objects.list_title", type=obj_type, connection=conn.name))
    table.add_column(t("common.name"))
    for name in names:
        table.add_row(escape(name))
    console.print(table)
    console.print(t("objects.count", count=len(names)))


def cmd_describe(args: argparse.Namespace) -> None:
    """Show one object's shape: columns, keys and indexes.

    Dispatches on what the object turns out to be rather than asking the user
    to say table or view. No row count in either format: a COUNT(*) is a full
    scan, which is why `psql \\d` does not show one either. `-f table` and
    `-f json` carry the same content -- one shape for the command, not two.
    """
    try:
        conn = catalogue.connection(args.connection)
        data = ops_schema.describe(conn, args.object)
    except OperationError as e:
        _fail_or_print(args, "describe", e.code, e.message)

    if args.format == "json":
        ok("describe", data)
        return

    kind = data["object_type"]
    definition = data.get("sql_definition", "")

    console.print(f"{escape(data['table'])} ({kind})")

    columns = Table(show_header=True)
    columns.add_column(t("common.column"))
    columns.add_column(t("common.type"))
    columns.add_column(t("common.nullable"))
    columns.add_column(t("common.key"))
    for c in data["columns"]:
        key = "PK" if c["is_pk"] else (f"-> {c['fk_ref']}" if c["fk_ref"] else "")
        columns.add_row(escape(c["name"]), escape(c["data_type"]),
                        t("common.yes_short") if c["nullable"] else t("common.no_short"), escape(key))
    console.print(columns)

    if data["indexes"]:
        console.print("\n" + t("describe.indexes_header"))
        for i in data["indexes"]:
            marker = "UNIQUE " if i["is_unique"] else ""
            console.print(f"  {escape(i['name'])}  {marker}({', '.join(i['columns'])})")

    if definition:
        console.print("\n" + t("describe.definition_header"))
        console.print(definition, markup=False, highlight=False)


def cmd_rows(args: argparse.Namespace) -> None:
    """Browse a table's rows, paged.

    No `--where`: `dbqm sql` already takes a predicate, and a filter
    expression here would be injection surface bought for nothing.
    """
    try:
        conn = catalogue.connection(args.connection)
        result = ops_schema.rows(conn, args.table, limit=args.limit, offset=args.offset)
    except OperationError as e:
        _fail_or_print(args, "rows", e.code, e.message)

    if args.format == "json":
        ok("rows", result.to_dict())
        return

    render._print_query_result(
        deps.QueryResult(
            query_name=result.table,
            connection_name=conn.name,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            elapsed=result.elapsed,
        ),
        args.format,
    )

    # `QueryResult` has no `total_count`, so the renderer cannot say it: a
    # human would see 100 rows of sixteen million and nothing to suggest there
    # is a second page. The JSON payload carries `total_count`; this is the
    # same fact for the reader. Only for `table` -- `csv` and `raw` are text
    # pipes, and a trailing sentence in them is corruption, not information.
    seen = result.offset + result.row_count
    if args.format == "table" and result.total_count > seen:
        console.print(
            t("rows.showing_page", seen=seen, total=result.total_count)
        )
