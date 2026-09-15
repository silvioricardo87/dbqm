"""Commands for curating saved queries and groups: add, update, rm, show, list.

Mirrors `dbqm.cli.commands.connection` -- the subparser shape, `_fail_or_print`,
the outcome printer, and `_*_rm`'s confirmation (refuse under a non-terminal
stdin rather than hang, and prompt on stderr so `-f json`'s stdout stays
JSON-only) are the same decisions, copied on purpose. `cmd_query` lives here
now; `cmd_group` (Task 4 of this sub-project) joins it later.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from rich.markup import escape
from rich.table import Table

from dbqm.cli import deps
from dbqm.cli.envelope import fail, ok
from dbqm.cli.errors import exit_for
from dbqm.cli.render import console

# Set by `build_parser` (in `dbqm.cli`) so `cmd_query` can print the group's
# own help (add/update/rm/show/list) on a bare `dbqm query`, the same way
# `connection._connection_parser` does for `dbqm connection`.
_query_parser: argparse.ArgumentParser | None = None


_QUERY_OUTCOME_TEXT = {
    "created": "criada",
    "updated": "atualizada",
    "removed": "removida",
}

# `outcome` (past participle, used in the Rich sentence) to the verb the
# envelope's `command` field uses instead (`query.add`, not `query.created`).
_QUERY_OUTCOME_VERB = {
    "created": "add",
    "updated": "update",
    "removed": "rm",
}


def _print_query_outcome(output_format: str, name: str, outcome: str) -> None:
    if output_format == "json":
        verbo = _QUERY_OUTCOME_VERB[outcome]
        ok(f"query.{verbo}", {"name": name, outcome: True})
        return
    console.print(f'Consulta "{escape(name)}" {_QUERY_OUTCOME_TEXT[outcome]}.')


def _fail_or_print(
    args: argparse.Namespace,
    command: str,
    code: str,
    message: str,
    *,
    extra: str | None = None,
) -> NoReturn:
    """Mirrors `connection._fail_or_print`: same branch point for `-f json`
    versus `table`, same exit code either way -- only what gets printed, and
    where, differs.
    """
    if args.format == "json":
        fail(command, code, message)
    console.print(f"[ds.op.failure]{escape(message)}[/ds.op.failure]")
    if extra:
        console.print(extra)
    sys.exit(int(exit_for(code)))


def _exit_with_errors(args: argparse.Namespace, command: str, errors: list[str]) -> NoReturn:
    if args.format == "json":
        fail(command, "validation", "; ".join(errors))
    for error in errors:
        console.print(f"[ds.op.failure]{escape(error)}[/ds.op.failure]")
    sys.exit(int(exit_for("validation")))


def _resolve_sql(args: argparse.Namespace, command: str) -> str | None:
    """The SQL text for `add`/`update`, or `None` if neither flag was given.

    `None` here (not `""`) is what lets `_query_values` drop the key entirely
    when the command line never mentions the query's SQL -- an `update
    --description` must not re-derive `table`/`columns`/`order_by` from
    whatever SQL happens to already be stored. `--sql-file` is read as UTF-8
    text; an unreadable path is `usage`, not a stack trace -- the file is
    something a script handed dbqm, not something dbqm already has.
    """
    sql_file = getattr(args, "sql_file", None)
    if sql_file:
        try:
            return Path(sql_file).read_text(encoding="utf-8")
        except OSError as exc:
            _fail_or_print(args, command, "usage",
                            f'Nao foi possivel ler "{sql_file}": {exc}')
    return getattr(args, "sql", None)


def _query_values(args: argparse.Namespace, sql: str | None) -> dict[str, object]:
    """Only the flags actually given. A flag left out must not overwrite.

    Mirrors `connection._connection_values`: `None` means "not mentioned on
    this command line" and is dropped here so `query_builder.build` sees an
    absent key -- which is what lets `query update --description` leave
    `sql`-derived fields, `column_maps`, `folder` and `is_favorite` exactly
    as they were.
    """
    values = {
        "name": args.name,
        "connection": args.connection,
        "description": args.description,
        "folder": args.folder,
        "is_favorite": args.is_favorite,
        "sql": sql,
    }
    return {key: value for key, value in values.items() if value is not None}


def _query_add(args: argparse.Namespace) -> None:
    from dbqm.core.query_builder import build, validate
    from dbqm.models.query import save_queries

    if deps.find_query(args.name) is not None:
        _exit_with_errors(args, "query.add", [f'Consulta "{args.name}" ja existe.'])

    sql = _resolve_sql(args, "query.add")
    values = _query_values(args, sql)

    errors = validate(values)
    if errors:
        _exit_with_errors(args, "query.add", errors)

    query = build(values)

    queries = deps.load_queries()
    queries.append(query)
    save_queries(queries)
    _print_query_outcome(args.format, query.name, "created")


def _query_update(args: argparse.Namespace) -> None:
    from dbqm.core.query_builder import build, validate
    from dbqm.models.query import save_queries

    existing = deps.find_query(args.name)
    if existing is None:
        _fail_or_print(args, "query.update", "not_found",
                        f'Consulta "{args.name}" nao encontrada.')

    sql = _resolve_sql(args, "query.update")
    values = _query_values(args, sql)

    # Validate the EFFECTIVE state an update would leave behind, not the
    # sparse `values` alone: a `query update NOME --description "..."` must
    # not fail validation just because --sql/--connection were not repeated
    # on this command line.
    merged = existing.to_dict()
    merged.update(values)
    errors = validate(merged)
    if errors:
        _exit_with_errors(args, "query.update", errors)

    # `build` gets the SPARSE `values`, never `merged`: `merged` always
    # carries a "sql" key (copied from `existing`), and if that reached
    # `build` it would re-derive `table`/`columns`/`order_by` from it even
    # when the user never passed --sql/--sql-file -- silently discarding a
    # manual edit to `table` the way `query_builder.build`'s docstring warns
    # against.
    query = build(values, existing)

    queries = deps.load_queries()
    index = next(i for i, q in enumerate(queries) if q.name == query.name)
    queries[index] = query
    save_queries(queries)
    _print_query_outcome(args.format, query.name, "updated")


def _query_show(args: argparse.Namespace) -> None:
    query = deps.find_query(args.name)
    if query is None:
        _fail_or_print(args, "query.show", "not_found",
                        f'Consulta "{args.name}" nao encontrada.')

    data = query.to_dict()

    if args.format == "json":
        ok("query.show", data)
        return

    table = Table(title=f"Consulta: {escape(query.name)}")
    table.add_column("Campo")
    table.add_column("Valor")
    for key, value in data.items():
        table.add_row(key, escape(str(value)))
    console.print(table)


def _query_rm(args: argparse.Namespace) -> None:
    from dbqm.models.query import delete_query

    if deps.find_query(args.name) is None:
        _fail_or_print(args, "query.rm", "not_found",
                        f'Consulta "{args.name}" nao encontrada.')

    if not args.yes:
        # Refuse rather than prompt when there is no terminal: a script that
        # hangs on an unanswerable question is worse than one that fails.
        if not sys.stdin.isatty():
            _fail_or_print(args, "query.rm", "usage",
                            "Use --yes para remover sem confirmacao.")
        # The prompt goes to stderr: `input(prompt)` writes it to stdout,
        # which would put prose on the stream the envelope owns.
        print(f'Remover a consulta "{args.name}"? [s/N] ', end="", file=sys.stderr, flush=True)
        resposta = input().strip().lower()
        if resposta not in ("s", "sim"):
            if args.format == "json":
                ok("query.rm", {"name": args.name, "removed": False})
            else:
                console.print("Cancelado.")
            return

    delete_query(args.name)
    _print_query_outcome(args.format, args.name, "removed")


def _query_list(args: argparse.Namespace) -> None:
    """Like `dbqm list queries`, plus an optional `--connection` filter that
    `list queries` has no room for (its `resource` is shared with
    connections/groups)."""
    items = deps.load_queries()
    connection = getattr(args, "connection", None)
    if connection:
        items = [q for q in items if q.connection == connection]

    if args.format == "json":
        data = [{"name": q.name, "connection": q.connection, "folder": q.folder,
                  "description": q.description,
                  "params": [p.name for p in q.params]} for q in items]
        ok("query.list", data)
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
        table.add_row(escape(q.name), escape(desc or "-"), f"[ds.identity]{escape(q.connection)}[/]",
                      escape(q.folder or "-"), escape(params), fav)
    console.print(table)


_QUERY_SUBCOMMANDS = {
    "add": _query_add,
    "update": _query_update,
    "rm": _query_rm,
    "show": _query_show,
    "list": _query_list,
}


def cmd_query(args: argparse.Namespace) -> None:
    """Manage saved queries."""
    subcommand = getattr(args, "subcommand", None)
    handler = _QUERY_SUBCOMMANDS.get(subcommand) if isinstance(subcommand, str) else None
    if handler is None:
        # A bare `dbqm query` prints the group's own help (add/update/rm/
        # show/list, with their flags) rather than a one-line reminder.
        if _query_parser is not None:
            _query_parser.print_help()
        else:
            console.print(
                "[ds.op.failure]Use: dbqm query add|update|rm|show|list"
                "[/ds.op.failure]"
            )
        sys.exit(int(exit_for("validation")))
    handler(args)
