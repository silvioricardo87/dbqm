"""Object browser: structure introspection, package parsing, and routine execution."""
from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any

from dbqm.i18n import t
from dbqm.core.read_only import ReadOnlyViolation


class ObjectNotFound(RuntimeError):
    """A statement failed and the catalogue confirms the name is not there.

    Raised only on the error path: checking existence up front would cost a
    metadata round trip on every successful call, which is the common case.
    Checking after a failure costs nothing when things work and gives an
    authoritative answer from the catalogue instead of matching the driver's
    wording for "does not exist" across dialects.
    """


class UnsupportedEngine(RuntimeError):
    """A capability that exists only on one engine was asked of another.

    Packages and routine introspection read `all_source` / `all_arguments`,
    which are Oracle data dictionary views. The other three engines model
    routines differently and are not covered. Raised before any cursor opens,
    so the caller gets a message instead of a driver traceback.
    """


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ColumnInfo:
    """Column metadata."""
    name: str
    data_type: str
    data_length: int
    data_precision: int | None
    data_scale: int | None
    nullable: bool
    is_pk: bool = False
    fk_ref: str = ""

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "data_length": self.data_length,
            "data_precision": self.data_precision,
            "data_scale": self.data_scale,
            "nullable": self.nullable,
            "is_pk": self.is_pk,
            "fk_ref": self.fk_ref,
        }


@dataclass
class IndexInfo:
    """Index metadata."""
    name: str
    columns: list[str] = field(default_factory=list)
    is_unique: bool = False

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "name": self.name,
            "columns": list(self.columns),
            "is_unique": self.is_unique,
        }


@dataclass
class TableStructure:
    """Full table structure result."""
    table: str
    columns: list[ColumnInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    elapsed: float = 0.0

    def to_dict(self) -> dict:
        """Wire shape. Nested dataclasses serialise through their own to_dict."""
        return {
            "table": self.table,
            "columns": [c.to_dict() for c in self.columns],
            "indexes": [i.to_dict() for i in self.indexes],
            "elapsed": self.elapsed,
        }


@dataclass
class RoutineParam:
    """Parameter of a stored routine."""
    name: str
    data_type: str
    direction: str  # IN, OUT, IN OUT
    default: str = ""

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "name": self.name,
            "data_type": self.data_type,
            "direction": self.direction,
            "default": self.default,
        }


@dataclass
class RoutineInfo:
    """Metadata for a single routine (procedure or function)."""
    name: str
    routine_type: str  # PROCEDURE or FUNCTION
    params: list[RoutineParam] = field(default_factory=list)
    return_type: str = ""

    @property
    def signature(self) -> str:
        """Format the parameter list as a human-readable signature string."""
        parts: list[str] = []
        for p in self.params:
            s = f"{p.name} {p.direction} {p.data_type}"
            if p.default:
                s += f" DEFAULT {p.default}"
            parts.append(s)
        sig = ", ".join(parts)
        if self.routine_type == "FUNCTION" and self.return_type:
            return f"({sig}) RETURN {self.return_type}"
        return f"({sig})"

    def to_dict(self) -> dict:
        """Wire shape. `signature` is a formatted string, not data — a
        consumer builds its own from `params`; it does not travel here."""
        return {
            "name": self.name,
            "routine_type": self.routine_type,
            "params": [p.to_dict() for p in self.params],
            "return_type": self.return_type,
        }


@dataclass
class PackageInfo:
    """Package metadata with its routines."""
    name: str
    owner: str
    routines: list[RoutineInfo] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Wire shape. Nested dataclasses serialise through their own to_dict."""
        return {
            "name": self.name,
            "owner": self.owner,
            "routines": [r.to_dict() for r in self.routines],
        }


@dataclass
class ViewInfo:
    """View metadata."""
    name: str
    owner: str
    sql_definition: str = ""

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "name": self.name,
            "owner": self.owner,
            "sql_definition": self.sql_definition,
        }


@dataclass
class RoutineExecutionResult:
    """Result of executing a routine."""
    success: bool
    output_lines: list[str] = field(default_factory=list)
    return_value: Any = None
    elapsed: float = 0.0
    error: str = ""
    #: {OUT or IN OUT parameter name: its value after the call}. Strings:
    #: the values travel back through DBMS_OUTPUT, which is text. Separate
    #: from `output_lines`, which now holds only what the routine itself
    #: printed.
    out_values: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "success": self.success,
            "output_lines": list(self.output_lines),
            "return_value": self.return_value,
            "out_values": dict(self.out_values),
            "elapsed": self.elapsed,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _output_marker() -> str:
    """The prefix the generated block puts on the lines it adds to
    DBMS_OUTPUT to carry OUT values and a function's return back.

    Generated per execution, not a constant: the values used to arrive as
    plain `NOME=valor` lines mixed into whatever the routine printed, so a
    routine printing its own `RETURN=...` shadowed the real return value and
    an OUT value was indistinguishable from output. No routine's source can
    contain a marker that did not exist when it was compiled.
    """
    return f"##dbqm{secrets.token_hex(4)}##"


def _is_numeric_type(dtype: str) -> bool:
    """Check if a data type is numeric."""
    numeric_types = {
        "NUMBER", "INTEGER", "INT", "SMALLINT", "FLOAT", "DOUBLE",
        "DECIMAL", "NUMERIC", "REAL", "BINARY_FLOAT", "BINARY_DOUBLE",
        "PLS_INTEGER", "BINARY_INTEGER", "NATURAL", "NATURALN",
        "POSITIVE", "POSITIVEN", "SIGNTYPE", "SIMPLE_INTEGER",
        "BIGINT", "TINYINT", "MONEY", "SMALLMONEY",
    }
    return dtype.upper().split("(")[0].strip() in numeric_types


# ---------------------------------------------------------------------------
# Object listing
# ---------------------------------------------------------------------------

_SQLITE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _sqlite_ident(name: str) -> str:
    """`name` double-quoted for a PRAGMA, which takes no bind parameters.

    Anything but a plain identifier is refused rather than interpolated: the
    catalogue is the one place a table name reaches SQL as text.
    """
    if not _SQLITE_IDENT.fullmatch(name):
        raise ValueError(t("object.invalid_name", name=name))
    return f'"{name}"'


def list_objects(db, db_type: str, obj_type: str) -> list[str]:
    """List database objects by type (TABLE, PACKAGE, VIEW, ROUTINE).

    Oracle: user_tables / user_objects / user_views.
    SQL Server, PostgreSQL, MySQL: information_schema.

    PACKAGE raises `UnsupportedEngine` on every engine but Oracle — packages
    are an Oracle concept, and an empty list would read as "there are none
    here" instead of "this question does not apply here". An unrecognized
    `obj_type` string still returns `[]`: that is an unknown key, not a lie.

    A known limit, not fixed here: for `obj_type="ROUTINE"` (on every engine)
    the query unions PROCEDURE and FUNCTION and returns only the name
    (`object_name`/`routine_name`) — the caller has no way to tell which is
    which. That is why the UI (`dbqm/ui/screens/browser.py`, the "Routines"
    filter) shows "Routine" for both. Fixing it properly means changing this
    function's return shape (from `list[str]` to something like
    `list[tuple[str, str]]`, name plus type per object) in EVERY ROUTINE
    branch below, not only Oracle's — out of scope for anyone who is only
    touching a screen.
    """
    obj_upper = obj_type.upper()

    if db_type != "oracle" and obj_upper == "PACKAGE":
        raise UnsupportedEngine(t("engine.packages_oracle_only", type=db_type))
    if db_type == "sqlite" and obj_upper in ("ROUTINE", "PROCEDURE", "FUNCTION"):
        # SQLite has no stored routines at all. An empty list would read as
        # "none here" instead of "this question does not apply here".
        raise UnsupportedEngine(t("engine.sqlite_no_routines"))

    cursor = db.cursor()
    try:
        if db_type == "oracle":
            if obj_upper == "TABLE":
                cursor.execute(
                    "SELECT table_name FROM user_tables ORDER BY table_name"
                )
            elif obj_upper == "PACKAGE":
                cursor.execute(
                    "SELECT object_name FROM user_objects "
                    "WHERE object_type = 'PACKAGE' ORDER BY object_name"
                )
            elif obj_upper == "VIEW":
                cursor.execute(
                    "SELECT view_name FROM user_views ORDER BY view_name"
                )
            elif obj_upper in ("PROCEDURE", "FUNCTION"):
                cursor.execute(
                    "SELECT object_name FROM user_objects "
                    "WHERE object_type = :t ORDER BY object_name",
                    {"t": obj_upper},
                )
            elif obj_upper == "ROUTINE":
                cursor.execute(
                    "SELECT object_name FROM user_objects "
                    "WHERE object_type IN ('PROCEDURE', 'FUNCTION') "
                    "ORDER BY object_name"
                )
            else:
                return []
        elif db_type == "sqlserver":
            if obj_upper == "TABLE":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_type = 'BASE TABLE' ORDER BY table_name"
                )
            elif obj_upper == "VIEW":
                cursor.execute(
                    "SELECT table_name FROM information_schema.views "
                    "ORDER BY table_name"
                )
            elif obj_upper == "ROUTINE":
                cursor.execute(
                    "SELECT routine_name FROM information_schema.routines "
                    "ORDER BY routine_name"
                )
            else:
                return []
        elif db_type == "postgresql":
            if obj_upper == "TABLE":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
                )
            elif obj_upper == "VIEW":
                cursor.execute(
                    "SELECT table_name FROM information_schema.views "
                    "WHERE table_schema = 'public' ORDER BY table_name"
                )
            elif obj_upper == "ROUTINE":
                cursor.execute(
                    "SELECT routine_name FROM information_schema.routines "
                    "WHERE routine_schema = 'public' ORDER BY routine_name"
                )
            else:
                return []
        elif db_type == "mysql":
            if obj_upper == "TABLE":
                cursor.execute(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY table_name"
                )
            elif obj_upper == "VIEW":
                cursor.execute(
                    "SELECT table_name FROM information_schema.views "
                    "WHERE table_schema = DATABASE() ORDER BY table_name"
                )
            elif obj_upper == "ROUTINE":
                cursor.execute(
                    "SELECT routine_name FROM information_schema.routines "
                    "WHERE routine_schema = DATABASE() ORDER BY routine_name"
                )
            else:
                return []
        elif db_type == "sqlite":
            # `sqlite_master` is the whole catalogue. Internal `sqlite_*`
            # objects (autoindexes, sequences) are not the user's.
            if obj_upper in ("TABLE", "VIEW"):
                cursor.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type = :t AND name NOT LIKE 'sqlite_%' ORDER BY name",
                    {"t": obj_upper.lower()},
                )
            else:
                return []
        else:
            return []

        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Table structure
# ---------------------------------------------------------------------------

def _get_pk_columns(cursor, db_type: str, table: str) -> set[str]:
    """Get primary key column names for a table."""
    if db_type == "oracle":
        cursor.execute("""
            SELECT acc.column_name
            FROM user_constraints ac
            JOIN user_cons_columns acc
                ON ac.constraint_name = acc.constraint_name
            WHERE ac.constraint_type = 'P'
              AND ac.table_name = :table_name
        """, {"table_name": table.upper()})
    elif db_type == "postgresql":
        cursor.execute("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = %(table_name)s
              AND tc.table_schema = 'public'
        """, {"table_name": table})
    elif db_type == "mysql":
        cursor.execute("""
            SELECT column_name
            FROM information_schema.key_column_usage
            WHERE table_schema = DATABASE()
              AND table_name = %(table_name)s
              AND constraint_name = 'PRIMARY'
        """, {"table_name": table})
    elif db_type == "sqlite":
        # (cid, name, type, notnull, dflt_value, pk) -- pk > 0 marks a key
        # column; the number is its position in a composite key.
        cursor.execute(f"PRAGMA table_info({_sqlite_ident(table)})")
        return {row[1].upper() for row in cursor.fetchall() if row[5]}
    else:
        cursor.execute("""
            SELECT ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name
                AND tc.constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_name = %(table_name)s
        """, {"table_name": table})

    return {row[0].upper() for row in cursor.fetchall()}


def _get_fk_map(cursor, db_type: str, table: str) -> dict[str, str]:
    """Get FK map: {column_name_upper: 'ref_table.ref_column'}.

    Oracle: all_constraints + all_cons_columns.
    SQL Server: information_schema.
    """
    fk_map: dict[str, str] = {}

    if db_type == "oracle":
        cursor.execute("""
            SELECT acc.column_name,
                   rcc.table_name AS ref_table,
                   rcc.column_name AS ref_column
            FROM all_constraints ac
            JOIN all_cons_columns acc
                ON ac.owner = acc.owner
                AND ac.constraint_name = acc.constraint_name
            JOIN all_cons_columns rcc
                ON ac.r_owner = rcc.owner
                AND ac.r_constraint_name = rcc.constraint_name
                AND acc.position = rcc.position
            WHERE ac.constraint_type = 'R'
              AND ac.table_name = :table_name
            ORDER BY acc.column_name
        """, {"table_name": table.upper()})
    elif db_type in ("postgresql", "mysql"):
        schema_filter = "'public'" if db_type == "postgresql" else "DATABASE()"
        cursor.execute(f"""
            SELECT kcu.column_name,
                   kcu2.table_name AS ref_table,
                   kcu2.column_name AS ref_column
            FROM information_schema.key_column_usage kcu
            JOIN information_schema.referential_constraints rc
                ON kcu.constraint_name = rc.constraint_name
                AND kcu.constraint_schema = rc.constraint_schema
            JOIN information_schema.key_column_usage kcu2
                ON rc.unique_constraint_name = kcu2.constraint_name
                AND rc.unique_constraint_schema = kcu2.constraint_schema
                AND kcu.ordinal_position = kcu2.ordinal_position
            WHERE kcu.table_name = %(table_name)s
              AND kcu.table_schema = {schema_filter}
            ORDER BY kcu.column_name
        """, {"table_name": table})
    elif db_type == "sqlite":
        # (id, seq, table, from, to, on_update, on_delete, match)
        cursor.execute(f"PRAGMA foreign_key_list({_sqlite_ident(table)})")
        for row in cursor.fetchall():
            fk_map[row[3].upper()] = f"{row[2]}.{row[4]}"
        return fk_map
    else:
        cursor.execute("""
            SELECT
                ccu_fk.column_name,
                ccu_pk.table_name AS ref_table,
                ccu_pk.column_name AS ref_column
            FROM information_schema.referential_constraints rc
            JOIN information_schema.constraint_column_usage ccu_fk
                ON rc.constraint_name = ccu_fk.constraint_name
                AND rc.constraint_schema = ccu_fk.constraint_schema
            JOIN information_schema.constraint_column_usage ccu_pk
                ON rc.unique_constraint_name = ccu_pk.constraint_name
                AND rc.unique_constraint_schema = ccu_pk.constraint_schema
            WHERE ccu_fk.table_name = %(table_name)s
            ORDER BY ccu_fk.column_name
        """, {"table_name": table})

    for row in cursor.fetchall():
        col_name, ref_table, ref_column = row[0], row[1], row[2]
        fk_map[col_name.upper()] = f"{ref_table}.{ref_column}"

    return fk_map


def _get_indexes(cursor, db_type: str, table: str) -> list[IndexInfo]:
    """Get indexes for a table."""
    indexes: list[IndexInfo] = []

    if db_type == "oracle":
        cursor.execute("""
            SELECT ui.index_name, ui.uniqueness
            FROM user_indexes ui
            WHERE ui.table_name = :table_name
            ORDER BY ui.index_name
        """, {"table_name": table.upper()})
        idx_rows = cursor.fetchall()

        for idx_name, uniqueness in idx_rows:
            cursor.execute("""
                SELECT column_name
                FROM user_ind_columns
                WHERE index_name = :idx_name
                ORDER BY column_position
            """, {"idx_name": idx_name})
            cols = [r[0] for r in cursor.fetchall()]
            indexes.append(IndexInfo(
                name=idx_name,
                columns=cols,
                is_unique=(uniqueness == "UNIQUE"),
            ))
    elif db_type == "postgresql":
        cursor.execute("""
            SELECT i.relname AS index_name,
                   ix.indisunique,
                   a.attname AS column_name,
                   array_position(ix.indkey, a.attnum) AS ordinal
            FROM pg_class t
            JOIN pg_index ix ON t.oid = ix.indrelid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
            WHERE t.relname = %(table_name)s
              AND t.relkind = 'r'
            ORDER BY i.relname, ordinal
        """, {"table_name": table})
        rows = cursor.fetchall()
        idx_dict: dict[str, IndexInfo] = {}
        for row in rows:
            idx_name, is_unique, col_name, _ = row[0], row[1], row[2], row[3]
            if idx_name not in idx_dict:
                idx_dict[idx_name] = IndexInfo(name=idx_name, columns=[], is_unique=bool(is_unique))
            idx_dict[idx_name].columns.append(col_name)
        indexes = list(idx_dict.values())
    elif db_type == "mysql":
        cursor.execute("""
            SELECT index_name, non_unique, column_name, seq_in_index
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = %(table_name)s
            ORDER BY index_name, seq_in_index
        """, {"table_name": table})
        rows = cursor.fetchall()
        idx_dict: dict[str, IndexInfo] = {}
        for row in rows:
            idx_name, non_unique, col_name, _ = row[0], row[1], row[2], row[3]
            if idx_name not in idx_dict:
                idx_dict[idx_name] = IndexInfo(name=idx_name, columns=[], is_unique=(non_unique == 0))
            idx_dict[idx_name].columns.append(col_name)
        indexes = list(idx_dict.values())
    elif db_type == "sqlite":
        # index_list: (seq, name, unique, origin, partial); index_info:
        # (seqno, cid, name). Autoindexes SQLite creates for constraints are
        # kept -- they are real indexes and a describe should say so.
        cursor.execute(f"PRAGMA index_list({_sqlite_ident(table)})")
        for _seq, idx_name, is_unique, _origin, _partial in cursor.fetchall():
            cursor.execute(f"PRAGMA index_info({_sqlite_ident(idx_name)})")
            cols = [r[2] for r in sorted(cursor.fetchall(), key=lambda r: r[0])]
            indexes.append(IndexInfo(name=idx_name, columns=cols, is_unique=bool(is_unique)))
    else:
        cursor.execute("""
            SELECT i.name AS index_name,
                   i.is_unique,
                   c.name AS column_name,
                   ic.key_ordinal
            FROM sys.indexes i
            JOIN sys.index_columns ic
                ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c
                ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE i.object_id = OBJECT_ID(%(table_name)s)
              AND i.type > 0
            ORDER BY i.name, ic.key_ordinal
        """, {"table_name": table})
        rows = cursor.fetchall()

        # Group by index name
        idx_dict: dict[str, IndexInfo] = {}
        for row in rows:
            idx_name, is_unique, col_name, _ = row[0], row[1], row[2], row[3]
            if idx_name not in idx_dict:
                idx_dict[idx_name] = IndexInfo(
                    name=idx_name,
                    columns=[],
                    is_unique=bool(is_unique),
                )
            idx_dict[idx_name].columns.append(col_name)
        indexes = list(idx_dict.values())

    return indexes


def get_table_structure(db, db_type: str, table: str) -> TableStructure:
    """Get a table's structure: columns (each with its PK flag and FK
    reference) and indexes. No row count — that would be a full scan, and a
    describe is meant to be instant.

    Oracle: user_tab_columns, user_constraints, user_indexes.
    SQL Server: information_schema.columns, sys.indexes.
    """
    start = time.time()
    cursor = db.cursor()

    try:
        # Columns
        columns: list[ColumnInfo] = []
        if db_type == "oracle":
            cursor.execute("""
                SELECT column_name, data_type, data_length,
                       data_precision, data_scale, nullable
                FROM user_tab_columns
                WHERE table_name = :table_name
                ORDER BY column_id
            """, {"table_name": table.upper()})
        elif db_type == "postgresql":
            cursor.execute("""
                SELECT column_name, data_type,
                       character_maximum_length,
                       numeric_precision, numeric_scale,
                       is_nullable
                FROM information_schema.columns
                WHERE table_name = %(table_name)s
                  AND table_schema = 'public'
                ORDER BY ordinal_position
            """, {"table_name": table})
        elif db_type == "mysql":
            cursor.execute("""
                SELECT column_name, data_type,
                       character_maximum_length,
                       numeric_precision, numeric_scale,
                       is_nullable
                FROM information_schema.columns
                WHERE table_name = %(table_name)s
                  AND table_schema = DATABASE()
                ORDER BY ordinal_position
            """, {"table_name": table})
        elif db_type == "sqlite":
            # Shaped like the other engines' rows so the loop below reads
            # one tuple form. The declared type is whatever the CREATE said,
            # possibly nothing -- SQLite allows an untyped column, and this
            # reports "" rather than inventing a type for it.
            cursor.execute(f"PRAGMA table_info({_sqlite_ident(table)})")
        else:
            cursor.execute("""
                SELECT column_name, data_type,
                       character_maximum_length,
                       numeric_precision, numeric_scale,
                       is_nullable
                FROM information_schema.columns
                WHERE table_name = %(table_name)s
                ORDER BY ordinal_position
            """, {"table_name": table})

        col_rows = cursor.fetchall()
        if db_type == "sqlite":
            col_rows = [
                (name, dtype or "", 0, None, None, "NO" if notnull else "YES")
                for _cid, name, dtype, notnull, _dflt, _pk in col_rows
            ]

        # PK and FK info
        pk_columns = _get_pk_columns(cursor, db_type, table)
        fk_map = _get_fk_map(cursor, db_type, table)

        for row in col_rows:
            col_name = row[0]
            data_type = row[1]
            data_length = row[2] or 0
            data_precision = row[3]
            data_scale = row[4]
            nullable_raw = row[5]

            if db_type == "oracle":
                nullable = (nullable_raw == "Y")
            else:
                nullable = (nullable_raw == "YES")

            columns.append(ColumnInfo(
                name=col_name,
                data_type=data_type,
                data_length=data_length,
                data_precision=data_precision,
                data_scale=data_scale,
                nullable=nullable,
                is_pk=(col_name.upper() in pk_columns),
                fk_ref=fk_map.get(col_name.upper(), ""),
            ))

        # Indexes
        indexes = _get_indexes(cursor, db_type, table)

        elapsed = time.time() - start
        return TableStructure(
            table=table,
            columns=columns,
            indexes=indexes,
            elapsed=elapsed,
        )
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Owner detection (Oracle)
# ---------------------------------------------------------------------------

def _detect_owner(cursor, db_type: str, obj_name: str, obj_type: str) -> str:
    """Detect the owner of an object via all_objects (Oracle only).

    Returns empty string for SQL Server or if not found.
    """
    if db_type != "oracle":
        return ""

    cursor.execute("""
        SELECT owner FROM all_objects
        WHERE object_name = :obj_name
          AND object_type = :obj_type
        ORDER BY
            CASE WHEN owner = USER THEN 0 ELSE 1 END
    """, {"obj_name": obj_name.upper(), "obj_type": obj_type.upper()})

    row = cursor.fetchone()
    return row[0] if row else ""


# ---------------------------------------------------------------------------
# Package routines parsing
# ---------------------------------------------------------------------------

def _parse_params(param_str: str) -> list[RoutineParam]:
    """Parse a PL/SQL parameter list string into RoutineParam objects.

    Handles: name [IN|OUT|IN OUT] type [DEFAULT|:= value]
    """
    params: list[RoutineParam] = []
    if not param_str or not param_str.strip():
        return params

    # Split on commas, but respect parentheses (e.g., NUMBER(10,2))
    raw_params: list[str] = []
    depth = 0
    current: list[str] = []
    for ch in param_str:
        if ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            raw_params.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        raw_params.append("".join(current).strip())

    for raw in raw_params:
        if not raw.strip():
            continue

        # Normalize whitespace
        tokens = raw.strip().split()
        if not tokens:
            continue

        name = tokens[0]
        direction = "IN"
        data_type = ""
        default = ""

        rest = tokens[1:]

        # Detect direction
        if len(rest) >= 2 and rest[0].upper() == "IN" and rest[1].upper() == "OUT":
            direction = "IN OUT"
            rest = rest[2:]
        elif len(rest) >= 1 and rest[0].upper() == "OUT":
            direction = "OUT"
            rest = rest[1:]
        elif len(rest) >= 1 and rest[0].upper() == "IN":
            direction = "IN"
            rest = rest[1:]

        # Detect default value (DEFAULT keyword or :=)
        default_idx = None
        for i, tok in enumerate(rest):
            if tok.upper() == "DEFAULT" or tok == ":=":
                default_idx = i
                break

        if default_idx is not None:
            data_type = " ".join(rest[:default_idx])
            default = " ".join(rest[default_idx + 1:])
        else:
            data_type = " ".join(rest)

        params.append(RoutineParam(
            name=name,
            data_type=data_type,
            direction=direction,
            default=default,
        ))

    return params


def _parse_spec_routines(spec_source: str) -> list[RoutineInfo]:
    """Parse a package spec source to extract routine declarations.

    Looks for PROCEDURE/FUNCTION declarations and their parameter lists.
    """
    routines: list[RoutineInfo] = []

    # Pattern to match PROCEDURE or FUNCTION declarations
    pattern = re.compile(
        r"\b(PROCEDURE|FUNCTION)\s+(\w+)",
        re.IGNORECASE,
    )

    for m in pattern.finditer(spec_source):
        routine_type = m.group(1).upper()
        routine_name = m.group(2)

        # Extract parameter list (content within parentheses after name)
        after = spec_source[m.end():]
        param_str = ""
        return_type = ""

        # Check if there are parameters (opening parenthesis)
        after_stripped = after.lstrip()
        if after_stripped.startswith("("):
            # Find matching closing parenthesis
            depth = 0
            start_idx = spec_source.index("(", m.end())
            for i in range(start_idx, len(spec_source)):
                if spec_source[i] == "(":
                    depth += 1
                elif spec_source[i] == ")":
                    depth -= 1
                    if depth == 0:
                        param_str = spec_source[start_idx + 1:i]
                        after = spec_source[i + 1:]
                        break

        # Check for RETURN type (functions)
        if routine_type == "FUNCTION":
            ret_match = re.match(r"\s*RETURN\s+(\S+)", after, re.IGNORECASE)
            if ret_match:
                return_type = ret_match.group(1).rstrip(";").strip()

        params = _parse_params(param_str)
        routines.append(RoutineInfo(
            name=routine_name,
            routine_type=routine_type,
            params=params,
            return_type=return_type,
        ))

    return routines


def list_package_routines(db, db_type: str, package: str) -> PackageInfo:
    """List routines in a package by parsing the spec source.

    Uses all_source to get the package spec, then parses declarations.
    """
    if db_type != "oracle":
        raise UnsupportedEngine(t("engine.packages_and_routines_oracle_only", type=db_type))
    cursor = db.cursor()
    try:
        owner = _detect_owner(cursor, db_type, package, "PACKAGE")

        # Get package spec source
        if not owner:
            owner_clause = "owner = USER"
            params: dict[str, str] = {"name": package.upper()}
        else:
            owner_clause = "owner = :owner"
            params = {"name": package.upper(), "owner": owner}

        cursor.execute(f"""
            SELECT text FROM all_source
            WHERE {owner_clause}
              AND name = :name
              AND type = 'PACKAGE'
            ORDER BY line
        """, params)

        rows = cursor.fetchall()
        spec_source = "".join(r[0] for r in rows)

        routines = _parse_spec_routines(spec_source) if spec_source else []

        return PackageInfo(
            name=package.upper(),
            owner=owner or "",
            routines=routines,
        )
    finally:
        cursor.close()


def _resolve_standalone_routine(cursor, routine_name: str) -> tuple[str, str]:
    """`(owner, object_type)` for a standalone routine, own schema first.

    `all_arguments` was filtered by `owner = USER`, so a routine the caller
    can execute but does not own came back with no arguments at all -- which
    is indistinguishable from a real zero-argument procedure, and the block
    was then built with no parameters. Resolving the owner first fixes that
    and answers two more questions in the same round trip: whether the name
    exists, and whether it is a PROCEDURE or a FUNCTION -- which the CLI had
    to guess at (it asks for PROCEDURE and re-tags afterwards) because
    nothing here told it.

    Returns `("", "")` when the name matches nothing the caller can see.
    """
    cursor.execute("""
        SELECT owner, object_type FROM all_objects
        WHERE object_name = :name
          AND object_type IN ('PROCEDURE', 'FUNCTION')
        ORDER BY
            CASE WHEN owner = USER THEN 0 ELSE 1 END, owner
    """, {"name": routine_name.upper()})
    row = cursor.fetchone()
    return (row[0], row[1]) if row else ("", "")


def get_standalone_routine_info(
    db, routine_name: str, routine_type: str = "PROCEDURE", db_type: str = "oracle",
) -> RoutineInfo:
    """Get parameter info for a standalone procedure or function from ALL_ARGUMENTS.

    `db_type` defaults to Oracle because every caller before 2.9.0 was
    Oracle; a caller that knows better passes it, and anything else is
    refused before `all_arguments` is asked of an engine that has no such
    view.

    `routine_type` is what the caller believes; when `all_objects` knows the
    object, what it says wins -- it is looking at the routine, the caller is
    guessing from a command line.
    """
    if db_type != "oracle":
        raise UnsupportedEngine(t("engine.routines_oracle_only", type=db_type))
    cursor = db.cursor()
    try:
        owner, real_kind = _resolve_standalone_routine(cursor, routine_name)
        if real_kind:
            routine_type = real_kind
        cursor.execute("""
            SELECT argument_name, data_type, in_out, default_value, position
            FROM all_arguments
            WHERE object_name = :name
              AND package_name IS NULL
              AND data_level = 0
              AND owner = NVL(:owner, USER)
            ORDER BY position
        """, {"name": routine_name.upper(), "owner": owner or None})

        params = []
        return_type = ""
        for row in cursor.fetchall():
            arg_name, dtype, in_out, default_val, position = row
            if position == 0 and not arg_name:
                # Position 0 with no name = function return type
                return_type = dtype or ""
                continue
            if not arg_name:
                continue
            direction = {"IN": "IN", "OUT": "OUT", "IN/OUT": "IN OUT"}.get(in_out, "IN")
            params.append(RoutineParam(
                name=arg_name,
                data_type=dtype or "",
                direction=direction,
                default=str(default_val).strip() if default_val else "",
            ))

        return RoutineInfo(
            name=routine_name.upper(),
            routine_type=routine_type.upper(),
            params=params,
            return_type=return_type,
        )
    finally:
        cursor.close()


def execute_standalone_routine(db, routine: RoutineInfo, param_values: dict[str, str], conn=None) -> RoutineExecutionResult:
    """Execute a standalone procedure or function (not inside a package)."""
    return execute_routine(db, "", routine, param_values, conn=conn)


# ---------------------------------------------------------------------------
# Package source
# ---------------------------------------------------------------------------

def get_package_source(db, db_type: str, package: str, source_type: str = "PACKAGE") -> str:
    """Get package spec or body source from all_source.

    source_type: 'PACKAGE' for spec, 'PACKAGE BODY' for body.
    """
    if db_type != "oracle":
        raise UnsupportedEngine(t("engine.packages_and_routines_oracle_only", type=db_type))
    cursor = db.cursor()
    try:
        owner = _detect_owner(cursor, db_type, package, "PACKAGE")

        if not owner:
            owner_clause = "owner = USER"
            params: dict[str, str] = {"name": package.upper(), "obj_type": source_type.upper()}
        else:
            owner_clause = "owner = :owner"
            params = {"name": package.upper(), "obj_type": source_type.upper(), "owner": owner}

        cursor.execute(f"""
            SELECT text FROM all_source
            WHERE {owner_clause}
              AND name = :name
              AND type = :obj_type
            ORDER BY line
        """, params)

        rows = cursor.fetchall()
        return "".join(r[0] for r in rows)
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# View definition
# ---------------------------------------------------------------------------

def get_view_definition(db, db_type: str, view: str) -> ViewInfo:
    """Get view SQL definition.

    Oracle: all_views.
    SQL Server: information_schema.views.
    """
    cursor = db.cursor()
    try:
        owner = ""
        sql_definition = ""

        if db_type == "oracle":
            owner = _detect_owner(cursor, db_type, view, "VIEW")

            if not owner:
                owner_clause = "owner = USER"
                params: dict[str, str] = {"view_name": view.upper()}
            else:
                owner_clause = "owner = :owner"
                params = {"view_name": view.upper(), "owner": owner}

            cursor.execute(f"""
                SELECT owner, text FROM all_views
                WHERE {owner_clause}
                  AND view_name = :view_name
            """, params)

            row = cursor.fetchone()
            if row:
                owner = row[0]
                sql_definition = row[1] or ""
        elif db_type == "postgresql":
            cursor.execute("""
                SELECT table_schema, view_definition
                FROM information_schema.views
                WHERE table_name = %(view_name)s
                  AND table_schema = 'public'
            """, {"view_name": view})
            row = cursor.fetchone()
            if row:
                owner = row[0] or ""
                sql_definition = row[1] or ""
        elif db_type == "mysql":
            cursor.execute("""
                SELECT table_schema, view_definition
                FROM information_schema.views
                WHERE table_name = %(view_name)s
                  AND table_schema = DATABASE()
            """, {"view_name": view})
            row = cursor.fetchone()
            if row:
                owner = row[0] or ""
                sql_definition = row[1] or ""
        elif db_type == "sqlite":
            # The whole CREATE VIEW statement, verbatim. No owner concept.
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'view' AND name = :v",
                {"v": view},
            )
            row = cursor.fetchone()
            if row:
                sql_definition = row[0] or ""
        else:
            cursor.execute("""
                SELECT table_schema, view_definition
                FROM information_schema.views
                WHERE table_name = %(view_name)s
            """, {"view_name": view})

            row = cursor.fetchone()
            if row:
                owner = row[0] or ""
                sql_definition = row[1] or ""

        return ViewInfo(
            name=view.upper() if db_type == "oracle" else view,
            owner=owner,
            sql_definition=sql_definition,
        )
    finally:
        cursor.close()


# ---------------------------------------------------------------------------
# Routine execution
# ---------------------------------------------------------------------------

def execute_routine(
    db,
    package: str,
    routine: RoutineInfo,
    param_values: dict[str, str],
    conn=None,
) -> RoutineExecutionResult:
    """Execute a package routine via anonymous PL/SQL block.

    Builds a DECLARE/BEGIN/END block, enables DBMS_OUTPUT, handles
    IN/OUT params and FUNCTION return values.

    Takes an open `db` handle rather than a `Connection`, so it cannot
    classify the statement it builds. When `conn` is given and read-only, it
    refuses outright: a routine can write regardless of the text that calls
    it, which is exactly why it is refused rather than classified.
    """
    if conn is not None and conn.db_type != "oracle":
        # Before read-only: there is nothing to protect on an engine with no
        # routines, and the anonymous block below is PL/SQL.
        raise UnsupportedEngine(
            t("engine.routines_oracle_only", type=conn.db_type)
        )
    if conn is not None and conn.read_only:
        raise ReadOnlyViolation(t("read_only.routine_refused", name=conn.name))
    start = time.time()
    cursor = db.cursor()

    try:
        # Enable DBMS_OUTPUT
        cursor.execute("BEGIN DBMS_OUTPUT.ENABLE(1000000); END;")

        # Build anonymous block
        declare_lines: list[str] = []
        begin_lines: list[str] = []
        bind_vars: dict[str, Any] = {}

        # Declare variables for OUT params and return value
        out_vars: dict[str, str] = {}  # param_name -> var_name
        return_var = ""

        if routine.routine_type == "FUNCTION" and routine.return_type:
            return_var = "v_return"
            declare_lines.append(f"  {return_var} {routine.return_type};")

        for p in routine.params:
            if p.direction in ("OUT", "IN OUT"):
                var_name = f"v_{p.name.lower()}"
                declare_lines.append(f"  {var_name} {p.data_type};")
                out_vars[p.name] = var_name

                # For IN OUT params, initialize with provided value via bind variable
                if p.direction == "IN OUT" and p.name in param_values:
                    init_bind = f"init_{p.name.lower()}"
                    val = param_values[p.name]
                    if _is_numeric_type(p.data_type):
                        try:
                            bind_vars[init_bind] = (
                                int(val) if "." not in val else float(val)
                            )
                        except (ValueError, TypeError):
                            bind_vars[init_bind] = val
                    else:
                        bind_vars[init_bind] = val
                    begin_lines.append(f"  {var_name} := :{init_bind};")

        # Build the call
        call_args: list[str] = []
        for p in routine.params:
            if p.direction == "IN":
                bind_name = f"p_{p.name.lower()}"
                val = param_values.get(p.name, p.default or "")
                if _is_numeric_type(p.data_type):
                    try:
                        bind_vars[bind_name] = (
                            int(val) if "." not in val else float(val)
                        )
                    except (ValueError, TypeError):
                        bind_vars[bind_name] = val
                else:
                    bind_vars[bind_name] = val
                call_args.append(f":{bind_name}")
            elif p.direction in ("OUT", "IN OUT"):
                call_args.append(out_vars[p.name])

        args_str = ", ".join(call_args)
        qualified_name = f"{package}.{routine.name}" if package else routine.name

        if routine.routine_type == "FUNCTION" and return_var:
            begin_lines.append(f"  {return_var} := {qualified_name}({args_str});")
        else:
            begin_lines.append(f"  {qualified_name}({args_str});")

        # Hand OUT params and the return value back, marked so they can be
        # told apart from what the routine printed itself.
        marker = _output_marker()
        for p_name, var_name in out_vars.items():
            begin_lines.append(
                f"  DBMS_OUTPUT.PUT_LINE('{marker}{p_name}=' || {var_name});"
            )

        if return_var:
            begin_lines.append(
                f"  DBMS_OUTPUT.PUT_LINE('{marker}RETURN=' || {return_var});"
            )

        # Assemble block
        block_parts: list[str] = []
        if declare_lines:
            block_parts.append("DECLARE")
            block_parts.extend(declare_lines)
        block_parts.append("BEGIN")
        block_parts.extend(begin_lines)
        block_parts.append("END;")

        block = "\n".join(block_parts)

        # Execute (caller handles commit/rollback)
        cursor.execute(block, bind_vars)

        # Read DBMS_OUTPUT lines
        from dbqm.core.query_engine import _read_dbms_output

        output_lines: list[str] = []
        out_values: dict[str, str] = {}
        return_value: Any = None

        for line_val in _read_dbms_output(cursor):
            if not line_val.startswith(marker):
                # Whatever the routine printed, verbatim -- including a line
                # that happens to read `RETURN=...`, which is the routine's
                # to print and no longer mistaken for the real return value.
                output_lines.append(line_val)
                continue
            name, _, value = line_val[len(marker):].partition("=")
            if name == "RETURN":
                return_value = value
            else:
                out_values[name] = value

        elapsed = time.time() - start
        return RoutineExecutionResult(
            success=True,
            output_lines=output_lines,
            return_value=return_value,
            out_values=out_values,
            elapsed=elapsed,
        )

    except Exception as e:
        elapsed = time.time() - start
        return RoutineExecutionResult(
            success=False,
            output_lines=[],
            return_value=None,
            elapsed=elapsed,
            error=str(e),
        )
    finally:
        cursor.close()
