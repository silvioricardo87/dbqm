"""Commands for inspecting the environment: test, list, ddl, history."""
from __future__ import annotations

import argparse
import sys
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.core.history import kind_label
from dbqm.i18n import t
from dbqm.ops import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console


def cmd_test(args: argparse.Namespace) -> None:
    """Test a database connection.

    Under `-f json` a connection that fails to connect is still reported
    (`{"ok": false}` inside the array) rather than aborting the command: the
    job of `test` is to say what happened to each connection, not to make the
    process itself fail because one of them is down. Only a name that does
    not exist is a `test` failure.
    """
    if args.connection == "__all__":
        connections = deps.load_connections()
        if args.format == "json":
            data = []
            for conn in connections:
                succeeded, msg = deps.test_connection(conn)
                data.append({"name": conn.name, "ok": succeeded, "message": msg})
            ok("test", data)
            return
        if not connections:
            console.print(f'[ds.text.muted]{t("connection.none_configured")}[/ds.text.muted]')
            return
        for conn in connections:
            succeeded, msg = deps.test_connection(conn)
            icon = "OK" if succeeded else "[ds.op.failure]FAIL[/ds.op.failure]"
            console.print(f"  {icon}  [ds.identity]{escape(conn.name)}[/]: {escape(msg.splitlines()[0])}")
        return

    conn = deps.find_connection(args.connection)
    if not conn:
        if args.format == "json":
            fail("test", "not_found", t("connection.not_found_named", name=args.connection))
        not_found = escape(t("connection.not_found_named", name=args.connection))
        console.print(f"[ds.op.failure]{not_found}[/ds.op.failure]")
        sys.exit(int(exit_for("not_found")))

    succeeded, msg = deps.test_connection(conn)
    if args.format == "json":
        ok("test", [{"name": conn.name, "ok": succeeded, "message": msg}])
        return
    if succeeded:
        console.print(escape(msg))
    else:
        # json never fails on this — see the docstring — but table's exit
        # code still names the condition: a connection that did not answer.
        console.print(f"[ds.op.failure]{escape(msg)}[/ds.op.failure]")
        sys.exit(int(exit_for("connection_failed")))


def cmd_list(args: argparse.Namespace) -> None:
    """List connections, queries, or groups."""
    resource = args.resource

    if resource == "connections":
        items = deps.load_connections()
        if args.format == "json":
            data = [{"name": c.name, "db_type": c.db_type, "target": c.display_target(),
                      "read_only": c.read_only} for c in items]
            ok("list.connections", data)
            return
        if not items:
            console.print(f'[ds.text.muted]{t("connection.none_configured")}[/ds.text.muted]')
            return
        table = Table(title=t("connection.list_title"))
        table.add_column(t("common.name"))
        table.add_column(t("common.type"))
        table.add_column(t("common.target"))
        for c in items:
            table.add_row(f"[ds.identity]{escape(c.name)}[/]", c.db_type, escape(c.display_target()))
        console.print(table)

    elif resource == "queries":
        items = deps.load_queries()
        if args.format == "json":
            data = [{"name": q.name, "connection": q.connection, "folder": q.folder,
                      "description": q.description,
                      "params": [p.name for p in q.params]} for q in items]
            ok("list.queries", data)
            return
        if not items:
            console.print(f'[ds.text.muted]{t("query.none_configured")}[/ds.text.muted]')
            return
        table = Table(title=t("query.list_title"))
        table.add_column(t("common.name"))
        table.add_column(t("common.description"))
        table.add_column(t("common.connection"))
        table.add_column(t("common.folder"))
        table.add_column(t("common.params"))
        table.add_column(t("common.favorite_short"))
        for q in items:
            params = ", ".join(p.name for p in q.params) or "-"
            fav = "*" if q.is_favorite else ""
            desc = q.description[:50] + "..." if len(q.description) > 50 else q.description
            table.add_row(q.name, desc or "-", f"[ds.identity]{q.connection}[/]", q.folder or "-", params, fav)
        console.print(table)

    elif resource == "groups":
        items = deps.load_groups()
        if args.format == "json":
            data = [{"name": g.name, "description": g.description, "queries": g.queries,
                      "join_key": g.join_key, "compare_columns": g.compare_columns} for g in items]
            ok("list.groups", data)
            return
        if not items:
            console.print(f'[ds.text.muted]{t("group.none_configured")}[/ds.text.muted]')
            return
        table = Table(title=t("group.list_title"))
        table.add_column(t("common.name"))
        table.add_column(t("common.description"))
        table.add_column(t("query.list_title"))
        table.add_column(t("common.key"))
        table.add_column(t("common.columns"))
        for g in items:
            desc = g.description[:50] + "..." if len(g.description) > 50 else g.description
            table.add_row(g.name, desc or "-", ", ".join(g.queries), g.join_key,
                         ", ".join(g.compare_columns))
        console.print(table)

    else:
        if args.format == "json":
            fail(f"list.{resource}", "usage", t("list.unknown_resource", resource=resource))
        unknown_one = escape(t("list.unknown_resource", resource=resource))
        console.print(f"[ds.op.failure]{unknown_one}[/ds.op.failure]")
        sys.exit(int(exit_for("usage")))


def _ddl_error_code(result: Any) -> str:
    """`not_found` when the object is absent, `sql_error` otherwise.

    `describe` and `rows` both answer `not_found` for a name that is not
    there; `ddl` said `sql_error`, which is the same disagreement B2 fixed
    one command over.

    Reads `result.not_found`. It used to match the end of the error text,
    which worked only while that text was one fixed sentence in one
    language.
    """
    return "not_found" if result.not_found else "sql_error"


def _fail_or_print(
    args: argparse.Namespace, command: str, code: str, message: str,
) -> NoReturn:
    """One branch point for `-f json`, like `query._fail_or_print`.

    Took the command name from a hard-coded "ddl" until 2.10.0, which is
    why `history` had no way to reach it."""
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    sys.exit(int(exit_for(code)))


def cmd_ddl(args: argparse.Namespace) -> None:
    """Extract DDL for a database object.

    Under `-f json` the per-object progress callback is routed to stderr --
    under table it stays on stdout as before, dim progress next to the human
    output.

    `--stdout` means what it says in both formats: nothing is written to
    disk. The payload keeps its `path` key and reports `None`, rather than
    dropping the key, so a consumer reads the same shape either way and
    learns the answer from the value. Every object's DDL travels inline in
    `objects` regardless, which is what makes skipping the file harmless.
    """
    conn = deps.find_connection(args.connection)
    if not conn:
        if args.format == "json":
            fail("ddl", "not_found", t("connection.not_found_named", name=args.connection))
        not_found = escape(t("connection.not_found_named", name=args.connection))
        console.print(f"[ds.op.failure]{not_found}[/ds.op.failure]")
        sys.exit(int(exit_for("not_found")))

    def on_progress(current, total, obj_type, obj_name):
        if args.format == "json":
            print(f"  [{current}/{total}] {obj_type}: {obj_name}", file=sys.stderr)
        else:
            console.print(f"  [{current}/{total}] {escape(obj_type)}: {escape(obj_name)}", style="dim")

    # `extract_ddl` opens its own handle and records every statement failure
    # into `result.errors`, so anything that escapes it is a failure to open --
    # the same call-site reasoning `query_engine` uses for `error_kind`.
    # Without this the exception reached `main.py` and became exit 1, "a bug in
    # dbqm", for a database that was merely unreachable.
    try:
        result = deps.extract_ddl(conn, args.object, on_progress=on_progress)
    except Exception as e:
        _fail_or_print(args, "ddl", "connection_failed", str(e))

    if args.format == "json":
        if result.errors and not result.objects:
            fail("ddl", _ddl_error_code(result), "; ".join(result.errors))
        if args.stdout:
            path = None
        else:
            dir_path, _ = deps.save_extraction(result)
            path = str(dir_path)
        data = {
            "objects": [o.to_dict() for o in result.objects],
            "path": path,
        }
        ok("ddl", data, warnings=result.errors or None)
        return

    if result.errors:
        for err in result.errors:
            console.print(f"[ds.op.failure]{escape(err)}[/ds.op.failure]")
        if not result.objects:
            sys.exit(int(exit_for("sql_error")))

    if args.stdout:
        for obj in result.objects:
            print(f"-- {obj.obj_type}: {obj.name}")
            print(obj.ddl)
            print()
    else:
        dir_path, _ = deps.save_extraction(result)
        console.print(t("ddl.saved_to", path=dir_path))


def cmd_history(args: argparse.Namespace) -> None:
    """View or clear execution history."""
    # Before the history is even read: `-n 0` fell through `args.limit or 20`
    # and silently meant the default, and `-n -5` reached `entries[:-5]` and
    # silently meant "all but the last five". `rows` validates `--limit` and
    # `--offset` the same way and for the same reason.
    if args.limit is not None and args.limit < 1:
        _fail_or_print(args, "history", "usage", t("history.limit_positive"))

    if args.clear:
        deps.clear_history()
        if args.format == "json":
            ok("history", [])
            return
        console.print(t("history.cleared"))
        return

    entries = deps.load_history()
    if not entries:
        if args.format == "json":
            ok("history", [])
            return
        console.print(f'[ds.text.muted]{t("history.empty")}[/ds.text.muted]')
        return

    limit = args.limit or 20
    entries = entries[:limit]

    if args.format == "json":
        data = [e.to_dict() for e in entries]
        ok("history", data)
        return

    table = Table(title=t("history.title", count=len(entries)))
    table.add_column(t("common.date"))
    table.add_column(t("common.type"))
    table.add_column(t("common.name"))
    table.add_column(t("common.connection"))
    table.add_column(t("common.rows"))
    table.add_column(t("common.time"))
    table.add_column(t("common.status"))
    for e in entries:
        status = ("OK" if e.success
                  else f'[ds.op.failure]{t("common.error_short")}[/ds.op.failure]')
        if e.all_match is not None:
            status = (f"[ds.verdict.match]{t('verdict.consistent')}[/]" if e.all_match
                      else f"[ds.verdict.diff]{t('verdict.divergent')}[/]")
        table.add_row(
            e.timestamp, kind_label(e.entry_type), e.name,
            f"[ds.identity]{e.connection}[/]" if e.connection else "-",
            str(e.row_count) if e.entry_type == "query" else "-",
            f"{e.elapsed:.2f}s", status,
        )
    console.print(table)
