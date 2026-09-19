"""Table browser with FK resolution."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


def _validate_identifier(name: str) -> str:
    """Validate and return a safe SQL identifier.

    Only allows alphanumeric, underscore, dot, hash, and dollar characters.
    Raises ValueError if the name contains unexpected characters.
    """
    if not re.match(r'^[\w#$.]+$', name):
        raise ValueError(f"Invalid identifier: {name!r}")
    return name


@dataclass
class FKInfo:
    """Foreign key metadata."""
    column: str
    ref_table: str
    ref_column: str

    def to_dict(self) -> dict:
        """Wire shape."""
        return {
            "column": self.column,
            "ref_table": self.ref_table,
            "ref_column": self.ref_column,
        }


@dataclass
class BrowseResult:
    """Result of browsing a table."""
    table: str
    connection_name: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    total_count: int
    elapsed: float
    limit: int
    offset: int
    fk_columns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Wire shape. `rows` holds raw driver values (`datetime`, `Decimal`,
        LOB, …) — JSON-safe only because `dbqm/cli/envelope.py` dumps with
        `default=str`. They are not FK-resolved labels either — those are
        baked into `rows` already by `browse_table`, so there is nothing
        further to nest here."""
        return {
            "table": self.table,
            "connection_name": self.connection_name,
            "columns": list(self.columns),
            "rows": [list(r) for r in self.rows],
            "row_count": self.row_count,
            "total_count": self.total_count,
            "elapsed": self.elapsed,
            "limit": self.limit,
            "offset": self.offset,
            "fk_columns": list(self.fk_columns),
        }


def list_tables(db, db_type: str) -> list[str]:
    """List available tables.

    Oracle: USER_TABLES (current user's tables).
    SQL Server: INFORMATION_SCHEMA.TABLES.
    """
    cursor = db.cursor()
    try:
        if db_type == "oracle":
            cursor.execute(
                "SELECT table_name FROM user_tables ORDER BY table_name"
            )
        elif db_type == "postgresql":
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name"
            )
        elif db_type == "mysql":
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' ORDER BY table_name"
            )
        elif db_type == "sqlite":
            cursor.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        else:
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' ORDER BY table_name"
            )
        return [row[0] for row in cursor.fetchall()]
    finally:
        cursor.close()


def get_foreign_keys(db, db_type: str, table: str) -> list[FKInfo]:
    """Get foreign keys for a table.

    Oracle: ALL_CONSTRAINTS + ALL_CONS_COLUMNS.
    SQL Server: INFORMATION_SCHEMA.
    """
    cursor = db.cursor()
    try:
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
            # (id, seq, table, from, to, ...) -- the shape the others select.
            safe = _validate_identifier(table)
            cursor.execute(f'PRAGMA foreign_key_list("{safe}")')
            return [
                FKInfo(column=row[3], ref_table=row[2], ref_column=row[4])
                for row in cursor.fetchall()
            ]
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

        return [
            FKInfo(column=row[0], ref_table=row[1], ref_column=row[2])
            for row in cursor.fetchall()
        ]
    except Exception:
        return []
    finally:
        cursor.close()


def detect_label_column(db, db_type: str, ref_table: str, pk_col: str) -> str | None:
    """Auto-detect the best label column from a referenced table.

    Heuristic: first VARCHAR/NVARCHAR column that is not the PK.
    """
    cursor = db.cursor()
    try:
        if db_type == "oracle":
            cursor.execute("""
                SELECT column_name
                FROM all_tab_columns
                WHERE table_name = :table_name
                  AND data_type IN ('VARCHAR2', 'NVARCHAR2', 'CHAR', 'NCHAR')
                  AND column_name != :pk_col
                ORDER BY column_id
            """, {"table_name": ref_table.upper(), "pk_col": pk_col.upper()})
        elif db_type in ("postgresql", "mysql"):
            schema_filter = "'public'" if db_type == "postgresql" else "DATABASE()"
            cursor.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %(table_name)s
                  AND table_schema = {schema_filter}
                  AND data_type IN ('character varying', 'varchar', 'text', 'char', 'character')
                  AND column_name != %(pk_col)s
                ORDER BY ordinal_position
            """, {"table_name": ref_table, "pk_col": pk_col})
        elif db_type == "sqlite":
            # No information_schema: read the declared types and pick the
            # first text-like column that is not the key, in table order.
            safe = _validate_identifier(ref_table)
            cursor.execute(f'PRAGMA table_info("{safe}")')
            for _cid, name, dtype, _nn, _d, _pk in cursor.fetchall():
                kind = (dtype or "").upper()
                if name != pk_col and any(t in kind for t in ("CHAR", "TEXT", "CLOB")):
                    return name
            return None
        else:
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %(table_name)s
                  AND data_type IN ('varchar', 'nvarchar', 'char', 'nchar')
                  AND column_name != %(pk_col)s
                ORDER BY ordinal_position
            """, {"table_name": ref_table, "pk_col": pk_col})

        row = cursor.fetchone()
        return row[0] if row else None
    except Exception:
        return None
    finally:
        cursor.close()


def build_fk_lookups(db, db_type: str, fk_list: list[FKInfo]) -> dict[str, dict]:
    """Build lookup dicts for FK resolution.

    Returns {fk_column: {pk_value: label_value}}.
    Best-effort: silently skips FKs that fail.
    """
    lookups: dict[str, dict] = {}
    for fk in fk_list:
        try:
            label_col = detect_label_column(db, db_type, fk.ref_table, fk.ref_column)
            if not label_col:
                continue

            cursor = db.cursor()
            try:
                ref_col = _validate_identifier(fk.ref_column)
                lbl_col = _validate_identifier(label_col)
                ref_tbl = _validate_identifier(fk.ref_table)
                if db_type in ("oracle", "postgresql", "sqlite"):
                    cursor.execute(
                        f'SELECT "{ref_col}", "{lbl_col}" FROM "{ref_tbl}"'
                    )
                elif db_type == "mysql":
                    cursor.execute(
                        f"SELECT `{ref_col}`, `{lbl_col}` FROM `{ref_tbl}`"
                    )
                else:
                    cursor.execute(
                        f"SELECT [{ref_col}], [{lbl_col}] FROM [{ref_tbl}]"
                    )
                lookups[fk.column] = {
                    row[0]: row[1] for row in cursor.fetchall() if row[1] is not None
                }
            finally:
                cursor.close()
        except Exception:
            continue

    return lookups


def browse_table(
    db,
    db_type: str,
    table: str,
    connection_name: str,
    limit: int = 100,
    offset: int = 0,
) -> BrowseResult:
    """Browse a table with FK resolution.

    Orchestrates: COUNT + SELECT + FK enrichment.
    """
    start = time.time()
    cursor = db.cursor()

    try:
        safe_table = _validate_identifier(table)

        # Total count
        if db_type in ("oracle", "postgresql", "sqlite"):
            cursor.execute(f'SELECT COUNT(*) FROM "{safe_table}"')
        elif db_type == "mysql":
            cursor.execute(f"SELECT COUNT(*) FROM `{safe_table}`")
        else:
            cursor.execute(f"SELECT COUNT(*) FROM [{safe_table}]")
        total_count = cursor.fetchone()[0]

        # Paginated SELECT
        if db_type == "oracle":
            cursor.execute(
                f'SELECT * FROM "{safe_table}" '
                f"OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY",
                {"off": offset, "lim": limit},
            )
        elif db_type == "postgresql":
            cursor.execute(
                f'SELECT * FROM "{safe_table}" LIMIT %(lim)s OFFSET %(off)s',
                {"lim": limit, "off": offset},
            )
        elif db_type == "mysql":
            cursor.execute(
                f"SELECT * FROM `{safe_table}` LIMIT %(lim)s OFFSET %(off)s",
                {"lim": limit, "off": offset},
            )
        elif db_type == "sqlite":
            cursor.execute(
                f'SELECT * FROM "{safe_table}" LIMIT :lim OFFSET :off',
                {"lim": limit, "off": offset},
            )
        else:
            cursor.execute(
                f"SELECT * FROM [{safe_table}] "
                f"ORDER BY (SELECT NULL) OFFSET %(off)s ROWS FETCH NEXT %(lim)s ROWS ONLY",
                {"off": offset, "lim": limit},
            )

        columns = [
            desc[0].lower() if desc[0] else f"col_{i}"
            for i, desc in enumerate(cursor.description or [])
        ]
        rows = [list(row) for row in cursor.fetchall()]
    finally:
        cursor.close()

    # FK resolution (best-effort)
    fk_columns: list[str] = []
    try:
        fk_list = get_foreign_keys(db, db_type, table)
        if fk_list:
            lookups = build_fk_lookups(db, db_type, fk_list)
            col_lower = [c.lower() for c in columns]

            for fk in fk_list:
                fk_col_lower = fk.column.lower()
                if fk_col_lower in col_lower and fk.column in lookups:
                    idx = col_lower.index(fk_col_lower)
                    lookup = lookups[fk.column]
                    fk_columns.append(fk_col_lower)
                    for row in rows:
                        val = row[idx]
                        if val in lookup:
                            row[idx] = f"{val} \u2192 {lookup[val]}"
    except Exception:
        pass

    elapsed = time.time() - start
    return BrowseResult(
        table=table,
        connection_name=connection_name,
        columns=columns,
        rows=rows,
        row_count=len(rows),
        total_count=total_count,
        elapsed=elapsed,
        limit=limit,
        offset=offset,
        fk_columns=fk_columns,
    )
