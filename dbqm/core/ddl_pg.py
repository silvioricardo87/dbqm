"""PostgreSQL DDL extraction via information_schema and pg_catalog."""
from __future__ import annotations

from dbqm.core.ddl_extractor import ExtractionResult, ExtractedObject


def extract_pg_ddl(db, object_name: str, result: ExtractionResult, on_progress=None):
    """Extract DDL for a PostgreSQL object (table, view, function)."""
    cursor = db.cursor()
    name_lower = object_name.strip().lower()

    try:
        # Detect object type
        cursor.execute("""
            SELECT table_type FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %(name)s
        """, {"name": name_lower})
        row = cursor.fetchone()

        if row:
            if row[0] == 'BASE TABLE':
                result.object_type = "TABLE"
                _extract_pg_table(cursor, name_lower, result, on_progress)
            elif row[0] == 'VIEW':
                result.object_type = "VIEW"
                _extract_pg_view(cursor, name_lower, result, on_progress)
            return

        # Check routines
        cursor.execute("""
            SELECT routine_type FROM information_schema.routines
            WHERE routine_schema = 'public' AND routine_name = %(name)s
        """, {"name": name_lower})
        row = cursor.fetchone()
        if row:
            result.object_type = row[0]
            _extract_pg_routine(cursor, name_lower, result, on_progress)
            return

        result.errors.append(f"Objeto '{object_name}' nao encontrado.")
    finally:
        cursor.close()


def _extract_pg_table(cursor, table: str, result: ExtractionResult, on_progress=None):
    """Build CREATE TABLE DDL from information_schema."""
    if on_progress:
        on_progress(1, 3, "TABLE", table)

    # Columns
    cursor.execute("""
        SELECT column_name, data_type, character_maximum_length,
               numeric_precision, numeric_scale, is_nullable,
               column_default
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %(table)s
        ORDER BY ordinal_position
    """, {"table": table})

    cols = []
    for col_name, dtype, char_len, num_prec, num_scale, nullable, default in cursor.fetchall():
        col_type = _pg_format_type(dtype, char_len, num_prec, num_scale)
        col_def = f"  {col_name} {col_type}"
        if default:
            col_def += f" DEFAULT {default}"
        if nullable == "NO":
            col_def += " NOT NULL"
        cols.append(col_def)

    ddl = f"CREATE TABLE {table} (\n" + ",\n".join(cols) + "\n);"
    result.objects.append(ExtractedObject(table, "TABLE", ddl))

    # Constraints
    if on_progress:
        on_progress(2, 3, "CONSTRAINTS", table)

    cursor.execute("""
        SELECT conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE conrelid = %(table)s::regclass
          AND n.nspname = 'public'
    """, {"table": table})

    for con_name, con_def in cursor.fetchall():
        con_ddl = f"ALTER TABLE {table} ADD CONSTRAINT {con_name} {con_def};"
        result.objects.append(ExtractedObject(con_name, "CONSTRAINT", con_ddl))

    # Indexes
    if on_progress:
        on_progress(3, 3, "INDEXES", table)

    cursor.execute("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = %(table)s
    """, {"table": table})

    for idx_name, idx_def in cursor.fetchall():
        result.objects.append(ExtractedObject(idx_name, "INDEX", idx_def + ";"))


def _extract_pg_view(cursor, view: str, result: ExtractionResult, on_progress=None):
    """Extract CREATE VIEW DDL."""
    if on_progress:
        on_progress(1, 1, "VIEW", view)

    cursor.execute("""
        SELECT pg_get_viewdef(%(view)s::regclass, true)
    """, {"view": view})
    row = cursor.fetchone()
    definition = row[0] if row else ""
    ddl = f"CREATE OR REPLACE VIEW {view} AS\n{definition}"
    result.objects.append(ExtractedObject(view, "VIEW", ddl))


def _extract_pg_routine(cursor, routine: str, result: ExtractionResult, on_progress=None):
    """Extract CREATE FUNCTION/PROCEDURE DDL."""
    if on_progress:
        on_progress(1, 1, "ROUTINE", routine)

    cursor.execute("""
        SELECT pg_get_functiondef(p.oid)
        FROM pg_proc p
        JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE p.proname = %(name)s AND n.nspname = 'public'
        LIMIT 1
    """, {"name": routine})
    row = cursor.fetchone()
    if row:
        result.objects.append(ExtractedObject(routine, "ROUTINE", row[0] + ";"))
    else:
        result.errors.append(f"Rotina '{routine}' nao encontrada ou sem permissao.")


def _pg_format_type(dtype: str, char_len, num_prec, num_scale) -> str:
    if dtype in ("character varying",) and char_len:
        return f"varchar({char_len})"
    if dtype == "character" and char_len:
        return f"char({char_len})"
    if dtype == "numeric" and num_prec:
        if num_scale:
            return f"numeric({num_prec},{num_scale})"
        return f"numeric({num_prec})"
    return dtype
