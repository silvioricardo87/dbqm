"""Commands for inspecting the environment: test, list, ddl, history."""
from __future__ import annotations

import argparse
import sys

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
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
            console.print("[ds.text.muted]Nenhuma conexao configurada.[/ds.text.muted]")
            return
        for conn in connections:
            succeeded, msg = deps.test_connection(conn)
            icon = "OK" if succeeded else "[ds.op.failure]FAIL[/ds.op.failure]"
            console.print(f"  {icon}  [ds.identity]{escape(conn.name)}[/]: {escape(msg.splitlines()[0])}")
        return

    conn = deps.find_connection(args.connection)
    if not conn:
        if args.format == "json":
            fail("test", "not_found", f"Conexao '{args.connection}' nao encontrada.")
        console.print(f"[ds.op.failure]Conexao '{escape(args.connection)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    succeeded, msg = deps.test_connection(conn)
    if args.format == "json":
        ok("test", [{"name": conn.name, "ok": succeeded, "message": msg}])
        return
    if succeeded:
        console.print(escape(msg))
    else:
        console.print(f"[ds.op.failure]{escape(msg)}[/ds.op.failure]")
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List connections, queries, or groups."""
    resource = args.resource

    if resource == "connections":
        items = deps.load_connections()
        if args.format == "json":
            data = [{"name": c.name, "db_type": c.db_type, "target": c.display_target()} for c in items]
            ok("list.connections", data)
            return
        if not items:
            console.print("[ds.text.muted]Nenhuma conexao configurada.[/ds.text.muted]")
            return
        table = Table(title="Conexoes")
        table.add_column("Nome")
        table.add_column("Tipo")
        table.add_column("Destino")
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
            console.print("[ds.text.muted]Nenhuma consulta configurada.[/ds.text.muted]")
            return
        table = Table(title="Consultas")
        table.add_column("Nome")
        table.add_column("Descricao")
        table.add_column("Conexao")
        table.add_column("Pasta")
        table.add_column("Parametros")
        table.add_column("Fav")
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
            console.print("[ds.text.muted]Nenhum grupo configurado.[/ds.text.muted]")
            return
        table = Table(title="Grupos")
        table.add_column("Nome")
        table.add_column("Descricao")
        table.add_column("Consultas")
        table.add_column("Chave")
        table.add_column("Colunas")
        for g in items:
            desc = g.description[:50] + "..." if len(g.description) > 50 else g.description
            table.add_row(g.name, desc or "-", ", ".join(g.queries), g.join_key,
                         ", ".join(g.compare_columns))
        console.print(table)

    else:
        if args.format == "json":
            fail(f"list.{resource}", "usage", f"Recurso desconhecido: {resource}")
        console.print(f"[ds.op.failure]Recurso desconhecido: {resource}[/ds.op.failure]")
        sys.exit(1)


def cmd_ddl(args: argparse.Namespace) -> None:
    """Extract DDL for a database object.

    Under `-f json` the per-object progress callback is routed to stderr —
    under table it stays on stdout as before, dim progress next to the human
    output. The extraction is always saved to disk under json (regardless of
    `--stdout`, which only matters when there is no envelope to carry the DDL
    text back to the caller already): the payload needs a `path` either way,
    and every object's DDL travels inline in `objects` too.
    """
    conn = deps.find_connection(args.connection)
    if not conn:
        if args.format == "json":
            fail("ddl", "not_found", f"Conexao '{args.connection}' nao encontrada.")
        console.print(f"[ds.op.failure]Conexao '{escape(args.connection)}' nao encontrada.[/ds.op.failure]")
        sys.exit(1)

    def on_progress(current, total, obj_type, obj_name):
        if args.format == "json":
            print(f"  [{current}/{total}] {obj_type}: {obj_name}", file=sys.stderr)
        else:
            console.print(f"  [{current}/{total}] {escape(obj_type)}: {escape(obj_name)}", style="dim")

    result = deps.extract_ddl(conn, args.object, on_progress=on_progress)

    if args.format == "json":
        if result.errors and not result.objects:
            fail("ddl", "sql_error", "; ".join(result.errors))
        dir_path, _ = deps.save_extraction(result)
        data = {
            "objects": [{"name": o.name, "obj_type": o.obj_type, "ddl": o.ddl}
                        for o in result.objects],
            "path": str(dir_path),
        }
        ok("ddl", data, warnings=result.errors or None)
        return

    if result.errors:
        for err in result.errors:
            console.print(f"[ds.op.failure]{escape(err)}[/ds.op.failure]")
        if not result.objects:
            sys.exit(1)

    if args.stdout:
        for obj in result.objects:
            print(f"-- {obj.obj_type}: {obj.name}")
            print(obj.ddl)
            print()
    else:
        dir_path, _ = deps.save_extraction(result)
        console.print(f"DDL salvo em: {dir_path}")


def cmd_history(args: argparse.Namespace) -> None:
    """View or clear execution history."""
    if args.clear:
        deps.clear_history()
        if args.format == "json":
            ok("history", [])
            return
        console.print("Historico limpo.")
        return

    entries = deps.load_history()
    if not entries:
        if args.format == "json":
            ok("history", [])
            return
        console.print("[ds.text.muted]Historico vazio.[/ds.text.muted]")
        return

    limit = args.limit or 20
    entries = entries[:limit]

    if args.format == "json":
        data = [e.to_dict() for e in entries]
        ok("history", data)
        return

    table = Table(title=f"Historico (ultimos {len(entries)})")
    table.add_column("Data")
    table.add_column("Tipo")
    table.add_column("Nome")
    table.add_column("Conexao")
    table.add_column("Registros")
    table.add_column("Tempo")
    table.add_column("Status")
    for e in entries:
        status = "OK" if e.success else "[ds.op.failure]ERRO[/ds.op.failure]"
        if e.all_match is not None:
            status = "[ds.verdict.match]CONSISTENTE[/]" if e.all_match else "[ds.verdict.diff]DIVERGENTE[/]"
        table.add_row(
            e.timestamp, e.entry_type, e.name,
            f"[ds.identity]{e.connection}[/]" if e.connection else "-",
            str(e.row_count) if e.entry_type == "query" else "-",
            f"{e.elapsed:.2f}s", status,
        )
    console.print(table)
