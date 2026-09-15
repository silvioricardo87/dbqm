"""Query rules shared by the TUI and the CLI.

Validation and the SQL-to-table/columns/order-by/params derivation used to
live inside `ui/screens/query_manage.py`, where only the TUI could reach
them -- `core/` must never import `ui/`. They live here now, and both front
ends call them.

The messages `validate` returns are read by a user, so they are Portuguese
without accents, like every other label in the program. They are *returned*
rather than raised: the TUI shows them with `notify(severity="error")` and
the CLI prints them and picks an exit code, and that choice is not this
module's business.
"""
from __future__ import annotations

from typing import Any

from dbqm.core.query_engine import detect_params, parse_sql
from dbqm.models.connection import find_connection
from dbqm.models.query import Query, QueryParam, load_queries, save_queries


def _text(values: dict[str, Any], key: str) -> str:
    return str(values.get(key) or "").strip()


def validate(values: dict[str, Any]) -> list[str]:
    """Every problem with `values`, as user-facing messages. Empty means valid.

    Wording matches `query_manage.py`'s `SqlPasteModal._save` byte for byte:
    that screen is what users read today, so this module was made to agree
    with it, not the other way round. The connection-existence check is new
    here -- the TUI's dropdown only ever offers connections that exist, so it
    never needed one, but a CLI `--connection` is free text.
    """
    errors: list[str] = []

    if not _text(values, "sql"):
        errors.append("Informe o SQL.")

    if not _text(values, "name"):
        errors.append("Informe o nome da consulta.")

    connection = _text(values, "connection")
    if not connection:
        errors.append("Selecione uma conexao.")
    elif find_connection(connection) is None:
        errors.append(f'Conexao "{connection}" nao encontrada.')

    return errors


def build(values: dict[str, Any], existing: Query | None = None) -> Query:
    """A `Query` from raw form/CLI values. Assumes `validate` passed.

    Never mutates `existing`; starts from it when given and overlays only
    the keys `values` actually sets. That is the whole point of this
    function: a CLI `update --description` must not erase `column_maps`,
    `is_favorite`, `folder`, or anything else the TUI authored and this call
    never mentions. `created_at` is carried over, never regenerated.

    `table`, `columns`, `order_by` and `params` are derived from `sql` via
    `parse_sql`/`detect_params` only when `values` sets `sql` -- exactly what
    `_save` did before this moved. When `sql` is absent, that derivation is
    left alone too, so a manual edit to `table` (the screen's "Tabela" edit)
    survives an unrelated `update --description`.
    """

    def _carry(key: str, default: str = "") -> str:
        if key in values:
            return _text(values, key)
        return getattr(existing, key) if existing is not None else default

    name = _carry("name")
    connection = _carry("connection")
    description = _carry("description")
    folder = _carry("folder")

    if "sql" in values:
        sql = _text(values, "sql")
        parsed = parse_sql(sql)
        table = parsed.get("table", "")
        columns = parsed.get("columns", [])
        order_by = parsed.get("order_by", "")
        params = [QueryParam(name=p) for p in detect_params(sql)]
    elif existing is not None:
        sql = existing.sql
        table = existing.table
        columns = list(existing.columns)
        order_by = existing.order_by
        params = list(existing.params)
    else:
        sql = ""
        table = ""
        columns = []
        order_by = ""
        params = []

    if "is_favorite" in values:
        is_favorite = bool(values["is_favorite"])
    elif existing is not None:
        is_favorite = existing.is_favorite
    else:
        is_favorite = False

    if "column_maps" in values:
        column_maps = dict(values["column_maps"] or {})
    elif existing is not None:
        column_maps = dict(existing.column_maps)
    else:
        column_maps = {}

    last_executed = _carry("last_executed")

    query = Query(
        name=name,
        connection=connection,
        sql=sql,
        table=table,
        description=description,
        params=params,
        columns=columns,
        column_maps=column_maps,
        order_by=order_by,
        folder=folder,
        is_favorite=is_favorite,
        last_executed=last_executed,
    )
    if existing is not None:
        query.created_at = existing.created_at
    return query


def upsert(values: dict[str, Any]) -> tuple[Query, bool]:
    """Save `values`, creating or replacing by name. Returns (query, created).

    This is what the TUI's Salvar means. The CLI does NOT use it: there,
    `add` on an existing name and `update` on a missing one have to be
    errors, so the command checks first and calls `build` itself.
    """
    queries = load_queries()
    name = _text(values, "name")
    index = next((i for i, q in enumerate(queries) if q.name == name), None)
    existing = queries[index] if index is not None else None
    query = build(values, existing)
    if index is None:
        queries.append(query)
    else:
        queries[index] = query
    save_queries(queries)
    return query, index is None
