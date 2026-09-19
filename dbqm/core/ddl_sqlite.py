"""DDL extraction for SQLite.

`sqlite_master` holds every object's CREATE statement verbatim, so there is
nothing to reconstruct: a table's DDL is the text SQLite itself would need to
recreate it, and its indexes and triggers each carry their own. The `sql`
column is NULL for objects SQLite created implicitly (autoindexes for UNIQUE
and PRIMARY KEY constraints); those are skipped, since the constraint that
produced them is already inside the table's CREATE.
"""
from __future__ import annotations

from typing import Any, Callable

from dbqm.i18n import t
from dbqm.core.ddl_extractor import ExtractedObject, ExtractionResult

ProgressCallback = Callable[[int, int, str, str], None]


def extract_sqlite_ddl(
    db: Any,
    object_name: str,
    result: ExtractionResult,
    on_progress: ProgressCallback | None = None,
) -> None:
    """Fill `result` with the object's DDL, or an error if it does not exist.

    Mirrors `ddl_pg.extract_pg_ddl`: detect the type first, then extract.
    Names are matched case-sensitively, which is how SQLite stores them.
    """
    cursor = db.cursor()
    name = object_name.strip()
    try:
        cursor.execute(
            "SELECT type, sql FROM sqlite_master WHERE name = :n AND sql IS NOT NULL",
            {"n": name},
        )
        row = cursor.fetchone()
        if row is None:
            result.errors.append(t("ddl.object_not_found", name=object_name))
            result.not_found = True
            return

        obj_type = str(row[0]).upper()
        result.object_type = obj_type
        result.object_name = name
        if obj_type == "TABLE":
            _extract_table(cursor, name, result, on_progress)
        else:
            if on_progress:
                on_progress(1, 1, obj_type, name)
            result.objects.append(ExtractedObject(name, obj_type, _terminated(row[1])))
    finally:
        cursor.close()


def _extract_table(
    cursor: Any,
    table: str,
    result: ExtractionResult,
    on_progress: ProgressCallback | None,
) -> None:
    """The table, then every index and trigger declared on it."""
    cursor.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = :n",
        {"n": table},
    )
    table_sql = cursor.fetchone()[0]

    cursor.execute(
        "SELECT type, name, sql FROM sqlite_master "
        "WHERE tbl_name = :n AND type IN ('index', 'trigger') AND sql IS NOT NULL "
        "ORDER BY type, name",
        {"n": table},
    )
    children = cursor.fetchall()

    total = 1 + len(children)
    if on_progress:
        on_progress(1, total, "TABLE", table)
    result.objects.append(ExtractedObject(table, "TABLE", _terminated(table_sql)))

    for i, (child_type, child_name, child_sql) in enumerate(children, start=2):
        kind = str(child_type).upper()
        if on_progress:
            on_progress(i, total, kind, child_name)
        result.objects.append(ExtractedObject(child_name, kind, _terminated(child_sql)))


def _terminated(sql: str) -> str:
    """`sqlite_master.sql` has no trailing terminator; the other extractors
    emit one, and a file of statements should run as-is."""
    text = sql.rstrip()
    return text if text.endswith(";") else text + ";"
