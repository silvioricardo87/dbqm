"""Oracle DDL extraction engine."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from dbqm.core.db_manager import get_connection
from dbqm.models.connection import Connection

EXPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "exports"


@dataclass
class ExtractedObject:
    name: str
    obj_type: str
    ddl: str


@dataclass
class ExtractionResult:
    object_name: str
    object_type: str
    owner: str
    connection_name: str
    objects: list[ExtractedObject] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _query_all(cursor, sql: str, params: dict | None = None) -> list[tuple]:
    if params:
        cursor.execute(sql, params)
    else:
        cursor.execute(sql)
    return cursor.fetchall()


def _query_one(cursor, sql: str, params: dict | None = None) -> tuple | None:
    rows = _query_all(cursor, sql, params)
    return rows[0] if rows else None


def _get_source(cursor, owner: str, name: str, obj_type: str) -> str:
    """Get source code from ALL_SOURCE."""
    rows = _query_all(cursor, """
        SELECT text FROM all_source
        WHERE owner = :owner AND name = :name AND type = :obj_type
        ORDER BY line
    """, {"owner": owner, "name": name, "obj_type": obj_type})
    return "".join(r[0] for r in rows)


def _try_dbms_metadata(cursor, obj_type: str, name: str, owner: str) -> str | None:
    """Try to get DDL via DBMS_METADATA. Returns None if not available."""
    try:
        cursor.execute("""
            SELECT DBMS_METADATA.GET_DDL(:obj_type, :name, :owner) FROM DUAL
        """, {"obj_type": obj_type, "name": name, "owner": owner})
        row = cursor.fetchone()
        if row and row[0]:
            ddl = row[0] if isinstance(row[0], str) else row[0].read()
            return ddl.strip()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Object detection
# ---------------------------------------------------------------------------

def detect_object(cursor, name: str) -> list[dict]:
    """Detect object type and owner from ALL_OBJECTS."""
    rows = _query_all(cursor, """
        SELECT owner, object_name, object_type
        FROM all_objects
        WHERE object_name = :name
          AND object_type IN (
              'TABLE','VIEW','PACKAGE','PROCEDURE','FUNCTION',
              'TRIGGER','SEQUENCE','TYPE','SYNONYM'
          )
        ORDER BY
            CASE object_type
                WHEN 'TABLE' THEN 1 WHEN 'VIEW' THEN 2
                WHEN 'PACKAGE' THEN 3 WHEN 'PROCEDURE' THEN 4
                WHEN 'FUNCTION' THEN 5 WHEN 'TRIGGER' THEN 6
                WHEN 'SEQUENCE' THEN 7 WHEN 'TYPE' THEN 8
                WHEN 'SYNONYM' THEN 9 ELSE 10
            END
    """, {"name": name.upper()})
    return [{"owner": r[0], "name": r[1], "type": r[2]} for r in rows]


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------

def _extract_table(cursor, owner: str, name: str, result: ExtractionResult):
    # DDL
    ddl = _try_dbms_metadata(cursor, "TABLE", name, owner)
    if not ddl:
        ddl = _build_table_ddl_fallback(cursor, owner, name)
    result.objects.append(ExtractedObject(name, "TABLE", ddl))

    # Indexes
    rows = _query_all(cursor, """
        SELECT index_name FROM all_indexes
        WHERE table_owner = :owner AND table_name = :name
        ORDER BY index_name
    """, {"owner": owner, "name": name})
    for (idx_name,) in rows:
        idx_ddl = _try_dbms_metadata(cursor, "INDEX", idx_name, owner)
        if not idx_ddl:
            idx_ddl = _build_index_ddl_fallback(cursor, owner, name, idx_name)
        result.objects.append(ExtractedObject(idx_name, "INDEX", idx_ddl))

    # Constraints
    rows = _query_all(cursor, """
        SELECT constraint_name, constraint_type, search_condition,
               r_owner, r_constraint_name
        FROM all_constraints
        WHERE owner = :owner AND table_name = :name
        ORDER BY
            CASE constraint_type
                WHEN 'P' THEN 1 WHEN 'U' THEN 2
                WHEN 'R' THEN 3 WHEN 'C' THEN 4 ELSE 5
            END
    """, {"owner": owner, "name": name})
    for row in rows:
        c_name, c_type, search_cond, r_owner, r_cname = row
        cons_ddl = _try_dbms_metadata(cursor, "CONSTRAINT", c_name, owner)
        if not cons_ddl:
            cons_ddl = _build_constraint_ddl_fallback(
                cursor, owner, name, c_name, c_type, search_cond, r_owner, r_cname
            )
        type_label = {"P": "PRIMARY KEY", "U": "UNIQUE", "R": "FOREIGN KEY", "C": "CHECK"}.get(c_type, c_type)
        result.objects.append(ExtractedObject(c_name, f"CONSTRAINT ({type_label})", cons_ddl))


def _build_table_ddl_fallback(cursor, owner: str, name: str) -> str:
    rows = _query_all(cursor, """
        SELECT column_name, data_type, data_length, data_precision,
               data_scale, nullable, data_default
        FROM all_tab_columns
        WHERE owner = :owner AND table_name = :name
        ORDER BY column_id
    """, {"owner": owner, "name": name})

    cols = []
    for col_name, dtype, dlen, dprec, dscale, nullable, ddefault in rows:
        col_def = f"  {col_name} {_format_column_type(dtype, dlen, dprec, dscale)}"
        if ddefault:
            col_def += f" DEFAULT {ddefault.strip()}"
        if nullable == "N":
            col_def += " NOT NULL"
        cols.append(col_def)

    return f"CREATE TABLE {owner}.{name} (\n" + ",\n".join(cols) + "\n);"


def _format_column_type(dtype: str, dlen: int, dprec, dscale) -> str:
    if dtype in ("VARCHAR2", "CHAR", "NVARCHAR2", "NCHAR", "RAW"):
        return f"{dtype}({dlen})"
    if dtype == "NUMBER":
        if dprec is not None:
            if dscale and dscale > 0:
                return f"NUMBER({dprec},{dscale})"
            return f"NUMBER({dprec})"
        return "NUMBER"
    return dtype


def _build_index_ddl_fallback(cursor, owner: str, table_name: str, idx_name: str) -> str:
    idx_info = _query_one(cursor, """
        SELECT uniqueness, index_type FROM all_indexes
        WHERE owner = :owner AND index_name = :idx_name
    """, {"owner": owner, "idx_name": idx_name})

    cols = _query_all(cursor, """
        SELECT column_name FROM all_ind_columns
        WHERE index_owner = :owner AND index_name = :idx_name
        ORDER BY column_position
    """, {"owner": owner, "idx_name": idx_name})

    col_list = ", ".join(c[0] for c in cols)
    unique = "UNIQUE " if idx_info and idx_info[0] == "UNIQUE" else ""
    return f"CREATE {unique}INDEX {owner}.{idx_name} ON {owner}.{table_name} ({col_list});"


def _build_constraint_ddl_fallback(
    cursor, owner, table_name, c_name, c_type, search_cond, r_owner, r_cname
) -> str:
    cols = _query_all(cursor, """
        SELECT column_name FROM all_cons_columns
        WHERE owner = :owner AND constraint_name = :c_name
        ORDER BY position
    """, {"owner": owner, "c_name": c_name})
    col_list = ", ".join(c[0] for c in cols)

    if c_type == "P":
        return f"ALTER TABLE {owner}.{table_name} ADD CONSTRAINT {c_name} PRIMARY KEY ({col_list});"
    elif c_type == "U":
        return f"ALTER TABLE {owner}.{table_name} ADD CONSTRAINT {c_name} UNIQUE ({col_list});"
    elif c_type == "R":
        ref = ""
        if r_owner and r_cname:
            ref_cols = _query_all(cursor, """
                SELECT table_name, column_name FROM all_cons_columns
                WHERE owner = :r_owner AND constraint_name = :r_cname
                ORDER BY position
            """, {"r_owner": r_owner, "r_cname": r_cname})
            if ref_cols:
                ref_table = ref_cols[0][0]
                ref_col_list = ", ".join(c[1] for c in ref_cols)
                ref = f" REFERENCES {r_owner}.{ref_table} ({ref_col_list})"
        return f"ALTER TABLE {owner}.{table_name} ADD CONSTRAINT {c_name} FOREIGN KEY ({col_list}){ref};"
    elif c_type == "C":
        cond = search_cond.strip() if search_cond else ""
        return f"ALTER TABLE {owner}.{table_name} ADD CONSTRAINT {c_name} CHECK ({cond});"
    return f"-- Constraint {c_name} type={c_type}"


# ---------------------------------------------------------------------------
# Package extraction
# ---------------------------------------------------------------------------

def _extract_package(cursor, owner: str, name: str, result: ExtractionResult):
    # Spec
    spec = _try_dbms_metadata(cursor, "PACKAGE_SPEC", name, owner)
    if not spec:
        src = _get_source(cursor, owner, name, "PACKAGE")
        spec = f"CREATE OR REPLACE {src}" if src else f"-- Package spec {name} not found"
    result.objects.append(ExtractedObject(name, "PACKAGE SPEC", spec))

    # Body
    body = _try_dbms_metadata(cursor, "PACKAGE_BODY", name, owner)
    if not body:
        src = _get_source(cursor, owner, name, "PACKAGE BODY")
        body = f"CREATE OR REPLACE {src}" if src else f"-- Package body {name} not found"
    result.objects.append(ExtractedObject(name, "PACKAGE BODY", body))

    # Dependencies (tables referenced)
    _extract_dependencies(cursor, owner, name, "PACKAGE", result)


# ---------------------------------------------------------------------------
# Procedure / Function / Trigger / View / Sequence / Type
# ---------------------------------------------------------------------------

def _extract_source_object(cursor, owner: str, name: str, obj_type: str, result: ExtractionResult):
    """Extract PROCEDURE, FUNCTION, or TRIGGER."""
    ddl = _try_dbms_metadata(cursor, obj_type, name, owner)
    if not ddl:
        src = _get_source(cursor, owner, name, obj_type)
        ddl = f"CREATE OR REPLACE {src}" if src else f"-- {obj_type} {name} not found"
    result.objects.append(ExtractedObject(name, obj_type, ddl))
    _extract_dependencies(cursor, owner, name, obj_type, result)


def _extract_view(cursor, owner: str, name: str, result: ExtractionResult):
    ddl = _try_dbms_metadata(cursor, "VIEW", name, owner)
    if not ddl:
        row = _query_one(cursor, """
            SELECT text FROM all_views WHERE owner = :owner AND view_name = :name
        """, {"owner": owner, "name": name})
        ddl = f"CREATE OR REPLACE VIEW {owner}.{name} AS\n{row[0]}" if row else f"-- View {name} not found"
    result.objects.append(ExtractedObject(name, "VIEW", ddl))
    _extract_dependencies(cursor, owner, name, "VIEW", result)


def _extract_sequence(cursor, owner: str, name: str, result: ExtractionResult):
    ddl = _try_dbms_metadata(cursor, "SEQUENCE", name, owner)
    if not ddl:
        row = _query_one(cursor, """
            SELECT min_value, max_value, increment_by, last_number, cache_size, cycle_flag, order_flag
            FROM all_sequences WHERE sequence_owner = :owner AND sequence_name = :name
        """, {"owner": owner, "name": name})
        if row:
            min_v, max_v, inc, last, cache, cycle, order = row
            ddl = (
                f"CREATE SEQUENCE {owner}.{name}\n"
                f"  START WITH {last}\n"
                f"  INCREMENT BY {inc}\n"
                f"  MINVALUE {min_v}\n"
                f"  MAXVALUE {max_v}\n"
                f"  {'CYCLE' if cycle == 'Y' else 'NOCYCLE'}\n"
                f"  {'ORDER' if order == 'Y' else 'NOORDER'}\n"
                f"  CACHE {cache};"
            )
        else:
            ddl = f"-- Sequence {name} not found"
    result.objects.append(ExtractedObject(name, "SEQUENCE", ddl))


def _extract_type(cursor, owner: str, name: str, result: ExtractionResult):
    spec = _try_dbms_metadata(cursor, "TYPE_SPEC", name, owner)
    if not spec:
        src = _get_source(cursor, owner, name, "TYPE")
        spec = f"CREATE OR REPLACE {src}" if src else f"-- Type spec {name} not found"
    result.objects.append(ExtractedObject(name, "TYPE SPEC", spec))

    body = _try_dbms_metadata(cursor, "TYPE_BODY", name, owner)
    if not body:
        src = _get_source(cursor, owner, name, "TYPE BODY")
        if src:
            body = f"CREATE OR REPLACE {src}"
            result.objects.append(ExtractedObject(name, "TYPE BODY", body))


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def _extract_dependencies(cursor, owner: str, name: str, obj_type: str, result: ExtractionResult):
    """Extract referenced tables/views via ALL_DEPENDENCIES."""
    rows = _query_all(cursor, """
        SELECT DISTINCT referenced_owner, referenced_name, referenced_type
        FROM all_dependencies
        WHERE owner = :owner AND name = :name AND type = :obj_type
          AND referenced_type IN ('TABLE', 'VIEW', 'SEQUENCE')
          AND referenced_owner NOT IN ('SYS', 'SYSTEM', 'PUBLIC')
        ORDER BY referenced_type, referenced_name
    """, {"owner": owner, "name": name, "obj_type": obj_type})

    for ref_owner, ref_name, ref_type in rows:
        result.dependencies.append(f"{ref_type} {ref_owner}.{ref_name}")


# ---------------------------------------------------------------------------
# Synonym resolution
# ---------------------------------------------------------------------------

def _resolve_synonym(cursor, owner: str, name: str) -> tuple[str, str, str] | None:
    """Resolve synonym to actual object."""
    row = _query_one(cursor, """
        SELECT table_owner, table_name, db_link
        FROM all_synonyms
        WHERE (owner = :owner OR owner = 'PUBLIC') AND synonym_name = :name
        ORDER BY CASE WHEN owner = 'PUBLIC' THEN 1 ELSE 0 END
    """, {"owner": owner, "name": name})
    if row and not row[2]:  # skip db links
        real_objs = detect_object(cursor, row[1])
        if real_objs:
            return real_objs[0]["owner"], real_objs[0]["name"], real_objs[0]["type"]
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

EXTRACT_MAP = {
    "TABLE": _extract_table,
    "PACKAGE": _extract_package,
    "PROCEDURE": lambda c, o, n, r: _extract_source_object(c, o, n, "PROCEDURE", r),
    "FUNCTION": lambda c, o, n, r: _extract_source_object(c, o, n, "FUNCTION", r),
    "TRIGGER": lambda c, o, n, r: _extract_source_object(c, o, n, "TRIGGER", r),
    "VIEW": _extract_view,
    "SEQUENCE": _extract_sequence,
    "TYPE": _extract_type,
}


def extract_ddl(conn: Connection, object_name: str, owner_filter: str | None = None) -> ExtractionResult:
    """Extract DDL for a given object name. Auto-detects type.

    Returns ExtractionResult with objects and a saved .sql file path.
    """
    db = get_connection(conn)
    cursor = db.cursor()
    name_upper = object_name.strip().upper()

    try:
        matches = detect_object(cursor, name_upper)

        if owner_filter:
            matches = [m for m in matches if m["owner"] == owner_filter.upper()]

        if not matches:
            # Try synonym resolution
            resolved = _resolve_synonym(cursor, conn.user.upper(), name_upper)
            if resolved:
                matches = [{"owner": resolved[0], "name": resolved[1], "type": resolved[2]}]

        if not matches:
            result = ExtractionResult(
                object_name=name_upper, object_type="UNKNOWN",
                owner="", connection_name=conn.name,
            )
            result.errors.append(f"Objeto '{name_upper}' nao encontrado.")
            return result

        obj = matches[0]
        result = ExtractionResult(
            object_name=obj["name"], object_type=obj["type"],
            owner=obj["owner"], connection_name=conn.name,
        )

        extractor = EXTRACT_MAP.get(obj["type"])
        if extractor:
            try:
                extractor(cursor, obj["owner"], obj["name"], result)
            except Exception as e:
                result.errors.append(f"Erro ao extrair {obj['type']}: {e}")
        else:
            result.errors.append(f"Tipo '{obj['type']}' nao suportado para extracao.")

        return result
    finally:
        cursor.close()
        db.close()


def save_extraction(result: ExtractionResult) -> str:
    """Save extraction result to a .sql file. Returns file path."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w]", "_", result.object_name)
    filename = f"{result.connection_name}_{safe_name}_{ts}.sql"
    filepath = EXPORTS_DIR / filename

    lines: list[str] = []
    lines.append(f"-- ============================================================")
    lines.append(f"-- DDL Extraction: {result.owner}.{result.object_name}")
    lines.append(f"-- Type: {result.object_type}")
    lines.append(f"-- Connection: {result.connection_name}")
    lines.append(f"-- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"-- ============================================================")
    lines.append("")

    for obj in result.objects:
        lines.append(f"-- ------------------------------------------------------------")
        lines.append(f"-- {obj.obj_type}: {obj.name}")
        lines.append(f"-- ------------------------------------------------------------")
        lines.append("")
        ddl = obj.ddl.rstrip()
        if not ddl.endswith(";"):
            ddl += ";"
        lines.append(ddl)
        lines.append("")
        lines.append("/")
        lines.append("")

    if result.dependencies:
        lines.append(f"-- ------------------------------------------------------------")
        lines.append(f"-- Dependencies")
        lines.append(f"-- ------------------------------------------------------------")
        for dep in result.dependencies:
            lines.append(f"-- {dep}")
        lines.append("")

    if result.errors:
        lines.append(f"-- ------------------------------------------------------------")
        lines.append(f"-- Errors during extraction")
        lines.append(f"-- ------------------------------------------------------------")
        for err in result.errors:
            lines.append(f"-- {err}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)
