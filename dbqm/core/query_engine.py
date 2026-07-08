"""Query execution engine."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import sqlparse

from dbqm.core.db_manager import get_connection
from dbqm.models.connection import Connection
from dbqm.models.query import Query, QueryParam

MAX_ROWS = 10_000


@dataclass
class QueryResult:
    query_name: str
    connection_name: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    elapsed: float
    success: bool = True
    error: str = ""


def _strip_leading_comments(sql: str) -> str:
    """Drop leading line (``--``) and block (``/* */``) comments plus blank
    lines, returning the SQL from its first significant token.

    Used only to *classify* a statement. The original text (comments intact)
    is what actually runs — Oracle accepts comments before a block, so there
    is no need to strip them from the executed SQL.
    """
    s = sql.lstrip()
    while s:
        if s.startswith("--"):
            nl = s.find("\n")
            if nl == -1:
                return ""
            s = s[nl + 1:].lstrip()
        elif s.startswith("/*"):
            end = s.find("*/")
            if end == -1:
                return ""
            s = s[end + 2:].lstrip()
        else:
            break
    return s


def _is_select_only(sql: str) -> bool:
    """Ensure the SQL is a SELECT statement (no DML/DDL)."""
    parsed = sqlparse.parse(_strip_leading_comments(sql))
    if not parsed:
        return False
    stmt_type = parsed[0].get_type()
    return stmt_type in ("SELECT", None)


_DDL_KEYWORDS = frozenset({
    "CREATE", "ALTER", "DROP", "TRUNCATE", "GRANT", "REVOKE",
    "COMMENT", "RENAME", "PURGE", "FLASHBACK", "ANALYZE",
})


_PLSQL_KEYWORDS = frozenset({"DECLARE", "BEGIN", "EXEC", "EXECUTE", "CALL"})


def classify_sql(sql: str) -> str:
    """Classify SQL statement type.

    Returns 'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DDL', 'PLSQL', 'EXPLAIN', or 'UNKNOWN'.
    """
    stripped = _strip_leading_comments(sql)
    first_word = stripped.split()[0].upper() if stripped else ""
    # Classify by leading keyword first, before tokenizing. This avoids running
    # sqlparse over the entire statement for named-object DDL (e.g. a
    # multi-thousand-line PACKAGE BODY) — wasteful, and historically fragile
    # against sqlparse token caps. PL/SQL keywords also take priority because
    # sqlparse reads BEGIN as a transaction boundary, not a PL/SQL block.
    if first_word in _PLSQL_KEYWORDS:
        return "PLSQL"
    if first_word == "EXPLAIN":
        return "EXPLAIN"
    if first_word in _DDL_KEYWORDS:
        return "DDL"
    if not stripped:
        return "UNKNOWN"
    # Only now fall back to sqlparse — needed to disambiguate SELECT vs DML and
    # to resolve leading keywords like WITH (CTE) that map to a SELECT.
    parsed = sqlparse.parse(stripped)
    if not parsed:
        return "UNKNOWN"
    stmt_type = parsed[0].get_type()
    if stmt_type in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        return stmt_type
    if first_word in ("SELECT", "INSERT", "UPDATE", "DELETE"):
        return first_word
    return "UNKNOWN"


def _normalize_plsql(sql: str) -> str:
    """Normalize PL/SQL ad-hoc input.

    - Strips the SQL*Plus block terminator (`/` on its own line).
    - Expands `EXEC`/`EXECUTE`/`CALL <body>` to `BEGIN <body>; END;`.
    - Leaves DECLARE/BEGIN blocks untouched (driver accepts them as-is).
    """
    s = sql.strip()
    s = re.sub(r"\s*\n\s*/\s*$", "", s)
    # Detect the verb on the comment-stripped text so a leading `-- note`
    # before EXEC/EXECUTE/CALL still expands correctly.
    significant = _strip_leading_comments(s)
    first = significant.split()[0].upper() if significant.split() else ""
    if first in ("EXEC", "EXECUTE", "CALL"):
        parts = significant.split(None, 1)
        body = parts[1] if len(parts) > 1 else ""
        body = body.rstrip(";").strip()
        s = f"BEGIN {body}; END;"
    return s


def _bind_params_oracle(sql: str, params: dict) -> tuple[str, dict]:
    """Oracle uses :param syntax natively."""
    return sql, params


def _bind_params_pyformat(sql: str, params: dict) -> tuple[str, dict]:
    """Convert :param to %(param)s for pyformat databases (SQL Server, PostgreSQL, MySQL)."""
    converted = sql
    for key in params:
        converted = re.sub(rf":({re.escape(key)})\b", rf"%(\1)s", converted)
    return converted, params


def execute_query(query: Query, conn: Connection, param_values: dict) -> QueryResult:
    """Execute a query against a connection with given parameter values."""
    sql = query.sql.strip().rstrip(";")

    if not _is_select_only(sql):
        return QueryResult(
            query_name=query.name,
            connection_name=conn.name,
            columns=[],
            rows=[],
            row_count=0,
            elapsed=0,
            success=False,
            error="Apenas comandos SELECT sao permitidos.",
        )

    db = None
    try:
        start = time.time()
        db = get_connection(conn)
        cursor = db.cursor()
        try:
            if conn.db_type == "oracle":
                sql, param_values = _bind_params_oracle(sql, param_values)
            else:
                sql, param_values = _bind_params_pyformat(sql, param_values)

            if param_values:
                cursor.execute(sql, param_values)
            else:
                cursor.execute(sql)

            columns = [desc[0].lower() if desc[0] else f"col_{i}" for i, desc in enumerate(cursor.description or [])]
            rows = [list(row) for row in cursor.fetchmany(MAX_ROWS)]
            elapsed = time.time() - start

            return QueryResult(
                query_name=query.name,
                connection_name=conn.name,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed=elapsed,
            )
        finally:
            cursor.close()
    except Exception as e:
        return QueryResult(
            query_name=query.name,
            connection_name=conn.name,
            columns=[],
            rows=[],
            row_count=0,
            elapsed=0,
            success=False,
            error=str(e).split('\n')[0][:500],
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


@dataclass
class AdhocResult:
    """Result of an ad-hoc SQL execution (SELECT or DML)."""
    sql_type: str
    connection_name: str
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    rows_affected: int = 0
    elapsed: float = 0.0
    success: bool = True
    error: str = ""
    committed: bool = False
    output_lines: list[str] = field(default_factory=list)


def _read_dbms_output(cursor) -> list[str]:
    """Drain buffered DBMS_OUTPUT lines from an Oracle session."""
    lines: list[str] = []
    status_var = cursor.var(int)
    line_var = cursor.var(str, 32767)
    while True:
        cursor.execute(
            "BEGIN DBMS_OUTPUT.GET_LINE(:line, :status); END;",
            {"line": line_var, "status": status_var},
        )
        if status_var.getvalue() != 0:
            break
        line_val = line_var.getvalue()
        if line_val is not None:
            lines.append(line_val)
    return lines


def execute_adhoc(sql: str, conn: Connection, param_values: dict, auto_commit: bool = False, capture_output: bool = False) -> AdhocResult | tuple[AdhocResult, Any]:
    """Execute an ad-hoc SQL (SELECT, DML, or DDL) against a connection.

    For SELECT: returns AdhocResult.
    For DML without auto_commit: returns (AdhocResult, db_connection) for manual commit/rollback.
    For DML with auto_commit: returns AdhocResult (committed).
    For DDL: executes and returns AdhocResult (DDL auto-commits in Oracle).
    For errors: returns AdhocResult with success=False.

    When `capture_output` is True (Oracle only), DBMS_OUTPUT is enabled and the
    buffered lines are drained into AdhocResult.output_lines for SELECT/DML too.
    Anonymous PL/SQL blocks always capture DBMS_OUTPUT regardless of the flag.
    """
    sql = sql.strip()
    sql_type = classify_sql(sql)
    # Strip trailing `;` only for SELECT/DML — Oracle rejects it there.
    # DDL and PL/SQL blocks must keep their internal/final `;` to compile
    # correctly (otherwise PLS-00103, leaving the object INVALID).
    if sql_type in ("SELECT", "INSERT", "UPDATE", "DELETE", "EXPLAIN"):
        sql = sql.rstrip(";")
    elif sql_type == "PLSQL":
        sql = _normalize_plsql(sql)

    if sql_type == "UNKNOWN":
        return AdhocResult(
            sql_type=sql_type,
            connection_name=conn.name,
            success=False,
            error="Tipo de SQL nao suportado. Use SELECT, INSERT, UPDATE, DELETE, DDL (CREATE/ALTER/DROP...) ou EXPLAIN PLAN.",
        )

    db = None
    try:
        start = time.time()
        db = get_connection(conn)
        cursor = db.cursor()

        if conn.db_type == "oracle":
            bound_sql, param_values = _bind_params_oracle(sql, param_values)
        else:
            bound_sql, param_values = _bind_params_pyformat(sql, param_values)

        capture_dbms_output = conn.db_type == "oracle" and (
            capture_output or sql_type == "PLSQL"
        )
        if capture_dbms_output:
            cursor.execute("BEGIN DBMS_OUTPUT.ENABLE(1000000); END;")

        if param_values:
            cursor.execute(bound_sql, param_values)
        else:
            cursor.execute(bound_sql)

        elapsed = time.time() - start

        if sql_type == "SELECT":
            columns = [desc[0].lower() if desc[0] else f"col_{i}" for i, desc in enumerate(cursor.description or [])]
            rows = [list(row) for row in cursor.fetchmany(MAX_ROWS)]
            # Drain after fetching rows — GET_LINE reuses the cursor.
            output_lines = _read_dbms_output(cursor) if capture_dbms_output else []
            cursor.close()
            return AdhocResult(
                sql_type=sql_type,
                connection_name=conn.name,
                columns=columns,
                rows=rows,
                row_count=len(rows),
                elapsed=elapsed,
                output_lines=output_lines,
            )
        elif sql_type == "DDL":
            cursor.close()
            # For DDL on Oracle, check compilation errors if applicable
            compilation_errors = _fetch_ddl_errors(db, sql, conn.db_type)
            db.close()
            db = None
            return AdhocResult(
                sql_type=sql_type,
                connection_name=conn.name,
                elapsed=elapsed,
                committed=True,
                error=compilation_errors,
                success=not compilation_errors,
            )
        elif sql_type == "PLSQL":
            output_lines = _read_dbms_output(cursor) if capture_dbms_output else []
            cursor.close()
            db.close()
            db = None
            return AdhocResult(
                sql_type=sql_type,
                connection_name=conn.name,
                elapsed=elapsed,
                committed=True,
                success=True,
                output_lines=output_lines,
            )
        elif sql_type == "EXPLAIN":
            # Oracle EXPLAIN PLAN inserts into PLAN_TABLE — no result set.
            # PostgreSQL/MySQL EXPLAIN returns the plan as rows.
            if cursor.description:
                columns = [desc[0].lower() if desc[0] else f"col_{i}" for i, desc in enumerate(cursor.description)]
                rows = [list(row) for row in cursor.fetchmany(MAX_ROWS)]
                cursor.close()
                return AdhocResult(
                    sql_type=sql_type,
                    connection_name=conn.name,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    elapsed=elapsed,
                )
            cursor.close()
            if conn.db_type == "oracle":
                db.commit()
            db.close()
            db = None
            return AdhocResult(
                sql_type=sql_type,
                connection_name=conn.name,
                elapsed=elapsed,
                committed=True,
                success=True,
            )
        else:
            rows_affected = cursor.rowcount
            output_lines = _read_dbms_output(cursor) if capture_dbms_output else []
            if auto_commit:
                db.commit()
                cursor.close()
                return AdhocResult(
                    sql_type=sql_type,
                    connection_name=conn.name,
                    rows_affected=rows_affected,
                    elapsed=elapsed,
                    committed=True,
                    output_lines=output_lines,
                )
            else:
                # Caller owns the connection for commit/rollback
                owned_db = db
                db = None  # prevent finally from closing it
                return AdhocResult(
                    sql_type=sql_type,
                    connection_name=conn.name,
                    rows_affected=rows_affected,
                    elapsed=elapsed,
                    output_lines=output_lines,
                ), owned_db

    except Exception as e:
        return AdhocResult(
            sql_type=sql_type,
            connection_name=conn.name,
            success=False,
            error=str(e).split('\n')[0][:500],
        )
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                pass


def execute_explain(sql: str, conn: Connection, param_values: dict) -> AdhocResult:
    """Run EXPLAIN PLAN against `sql` and return the execution plan as text.

    Oracle: wraps the query in `EXPLAIN PLAN SET STATEMENT_ID = ... FOR <sql>`,
    then queries `DBMS_XPLAN.DISPLAY` and returns the plan rows.

    PostgreSQL/MySQL: prepends `EXPLAIN` and returns the plan rows directly.

    SQL Server is not yet supported.

    The returned AdhocResult has sql_type='EXPLAIN', columns=['plan'], and
    rows=[[line], ...] (one row per plan line).
    """
    sql = sql.strip().rstrip(";")
    # Refuse if the user already passed an EXPLAIN — we'd double-wrap.
    first_word = sql.split()[0].upper() if sql.split() else ""
    if first_word == "EXPLAIN":
        return AdhocResult(
            sql_type="EXPLAIN",
            connection_name=conn.name,
            success=False,
            error="Passe apenas a query (sem EXPLAIN PLAN FOR) ao usar --explain.",
        )

    if conn.db_type == "oracle":
        statement_id = f"dbqm_{int(time.time() * 1_000_000)}"
        explain_sql = f"EXPLAIN PLAN SET STATEMENT_ID = '{statement_id}' FOR {sql}"
        display_sql = (
            "SELECT PLAN_TABLE_OUTPUT FROM TABLE("
            f"DBMS_XPLAN.DISPLAY(NULL, '{statement_id}', 'TYPICAL'))"
        )
        db = None
        try:
            start = time.time()
            db = get_connection(conn)
            cursor = db.cursor()
            if param_values:
                cursor.execute(explain_sql, param_values)
            else:
                cursor.execute(explain_sql)
            cursor.execute(display_sql)
            rows = [list(row) for row in cursor.fetchmany(MAX_ROWS)]
            cursor.close()
            elapsed = time.time() - start
            return AdhocResult(
                sql_type="EXPLAIN",
                connection_name=conn.name,
                columns=["plan"],
                rows=rows,
                row_count=len(rows),
                elapsed=elapsed,
            )
        except Exception as e:
            return AdhocResult(
                sql_type="EXPLAIN",
                connection_name=conn.name,
                success=False,
                error=str(e).split("\n")[0][:500],
            )
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    if conn.db_type in ("postgresql", "mysql"):
        return execute_adhoc(f"EXPLAIN {sql}", conn, param_values)  # type: ignore[return-value]

    return AdhocResult(
        sql_type="EXPLAIN",
        connection_name=conn.name,
        success=False,
        error=f"--explain ainda nao e suportado para {conn.db_type}.",
    )


def _fetch_ddl_errors(db, sql: str, db_type: str) -> str:
    """After DDL execution, check for compilation errors (Oracle CREATE/ALTER)."""
    if db_type != "oracle":
        return ""
    upper = sql.upper()
    if not any(kw in upper for kw in ("CREATE", "ALTER")):
        return ""
    # Extract object type and name from DDL
    m = re.search(
        r"(?:CREATE\s+(?:OR\s+REPLACE\s+)?|ALTER\s+)"
        r"(PACKAGE\s+BODY|PACKAGE|PROCEDURE|FUNCTION|TRIGGER|TYPE\s+BODY|TYPE|VIEW)"
        r"\s+(?:(\w+)\.)?(\w+)",
        sql, re.IGNORECASE,
    )
    if not m:
        return ""
    obj_type = m.group(1).upper()
    owner = m.group(2).upper() if m.group(2) else None
    obj_name = m.group(3).upper()
    try:
        cursor = db.cursor()
        if owner:
            cursor.execute(
                "SELECT line, position, text FROM all_errors "
                "WHERE name = :n AND type = :t AND owner = :o ORDER BY sequence",
                {"n": obj_name, "t": obj_type, "o": owner},
            )
        else:
            cursor.execute(
                "SELECT line, position, text FROM user_errors "
                "WHERE name = :n AND type = :t ORDER BY sequence",
                {"n": obj_name, "t": obj_type},
            )
        errors = cursor.fetchall()
        cursor.close()
        if not errors:
            return ""
        lines = [f"Linha {row[0]}, Col {row[1]}: {row[2].strip()}" for row in errors]
        return "\n".join(lines)
    except Exception:
        return ""


def parse_sql(sql: str) -> dict:
    """Parse a raw SQL string and extract table, columns, where conditions, order by."""
    sql = sql.strip().rstrip(";")
    result = {
        "table": "",
        "columns": [],
        "where_values": {},
        "order_by": "",
        "sql_clean": sql,
    }

    upper = sql.upper()

    # Extract table from FROM clause
    from_match = re.search(r"\bFROM\s+(\S+)", sql, re.IGNORECASE)
    if from_match:
        result["table"] = from_match.group(1)

    # Extract aliases from SELECT ... FROM
    select_match = re.search(r"SELECT\s+(.*?)\s+FROM\s+", sql, re.IGNORECASE | re.DOTALL)
    if select_match:
        select_block = select_match.group(1)
        aliases = []
        # Split by comma, but respect parentheses and CASE blocks
        depth = 0
        current = ""
        for ch in select_block:
            if ch in ("(", ):
                depth += 1
            elif ch in (")", ):
                depth -= 1
            elif ch == "," and depth == 0:
                aliases.append(_extract_alias(current.strip()))
                current = ""
                continue
            current += ch
        if current.strip():
            aliases.append(_extract_alias(current.strip()))
        result["columns"] = [a for a in aliases if a]

    # Extract literal values from WHERE for parameterization
    where_match = re.search(r"\bWHERE\s+(.*?)(?:\bORDER\s+BY\b|\bGROUP\s+BY\b|\bHAVING\b|$)", sql, re.IGNORECASE | re.DOTALL)
    if where_match:
        where_block = where_match.group(1)
        # Find patterns like COLUMN = 'value' or COLUMN = value
        eq_matches = re.finditer(r"(\w+)\s*=\s*'([^']*)'", where_block)
        for m in eq_matches:
            col_name = m.group(1).lower()
            result["where_values"][col_name] = m.group(2)

    # Extract ORDER BY
    order_match = re.search(r"\bORDER\s+BY\s+(.*?)$", sql, re.IGNORECASE | re.DOTALL)
    if order_match:
        result["order_by"] = order_match.group(1).strip()

    return result


def parse_dml_literals(sql: str) -> dict[str, str]:
    """Extract literal values from DML statements (INSERT/UPDATE/DELETE).

    Returns dict of {column_name: literal_value}.
    """
    sql_type = classify_sql(sql)
    literals = {}

    if sql_type == "INSERT":
        col_match = re.search(r"INSERT\s+INTO\s+\S+\s*\(([^)]+)\)", sql, re.IGNORECASE)
        val_match = re.search(r"VALUES\s*\(([^)]+)\)", sql, re.IGNORECASE)
        if col_match and val_match:
            cols = [c.strip() for c in col_match.group(1).split(",")]
            raw_vals = re.findall(r"'([^']*)'|(\d+(?:\.\d+)?)", val_match.group(1))
            vals = [v[0] if v[0] else v[1] for v in raw_vals]
            for col, val in zip(cols, vals):
                literals[col.lower()] = val

    elif sql_type == "UPDATE":
        set_match = re.search(r"\bSET\s+(.*?)(?:\bWHERE\b|$)", sql, re.IGNORECASE | re.DOTALL)
        if set_match:
            for m in re.finditer(r"(\w+)\s*=\s*'([^']*)'", set_match.group(1)):
                literals[m.group(1).lower()] = m.group(2)
        where_match = re.search(r"\bWHERE\s+(.*?)$", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            for m in re.finditer(r"(\w+)\s*=\s*'([^']*)'", where_match.group(1)):
                literals[m.group(1).lower()] = m.group(2)

    elif sql_type == "DELETE":
        where_match = re.search(r"\bWHERE\s+(.*?)$", sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            for m in re.finditer(r"(\w+)\s*=\s*'([^']*)'", where_match.group(1)):
                literals[m.group(1).lower()] = m.group(2)

    return literals


def _extract_alias(expr: str) -> str:
    """Extract alias from a SELECT expression like 'COL AS alias' or 'COL alias' or just 'COL'."""
    # Check for AS keyword
    as_match = re.search(r"\bAS\s+(\w+)\s*$", expr, re.IGNORECASE)
    if as_match:
        return as_match.group(1).lower()
    # Check for CASE...END alias
    end_match = re.search(r"\bEND\s+(\w+)\s*$", expr, re.IGNORECASE)
    if end_match:
        return end_match.group(1).lower()
    # Just a column name
    parts = expr.strip().split()
    if len(parts) == 1:
        return parts[0].lower()
    # Last word might be alias
    last = parts[-1]
    if re.match(r"^\w+$", last) and last.upper() not in ("FROM", "AS", "END"):
        return last.lower()
    return expr.strip().split(".")[- 1].lower() if "." in expr else expr.strip().lower()


def detect_params(sql: str) -> list[str]:
    """Detect :param bind variables in SQL."""
    return list(set(re.findall(r":(\w+)", sql)))


def replace_literals_with_params(sql: str, replacements: dict[str, str]) -> str:
    """Replace literal values in WHERE with :param bind variables.

    replacements: {param_name: literal_value}
    """
    for param_name, literal_value in replacements.items():
        sql = sql.replace(f"'{literal_value}'", f":{param_name}")
        sql = sql.replace(literal_value, f":{param_name}")
    return sql


def generate_sql_text(sql: str, param_values: dict) -> str:
    """Replace :param bind variables with actual values in the SQL text."""
    result = sql
    for param, value in param_values.items():
        try:
            float(value)
            replacement = str(value)
        except (ValueError, TypeError):
            replacement = f"'{value}'"
        result = re.sub(rf":{re.escape(param)}\b", replacement, result)
    return result
