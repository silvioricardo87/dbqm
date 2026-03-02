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


def _is_select_only(sql: str) -> bool:
    """Ensure the SQL is a SELECT statement (no DML/DDL)."""
    parsed = sqlparse.parse(sql.strip())
    if not parsed:
        return False
    stmt_type = parsed[0].get_type()
    return stmt_type in ("SELECT", None)


def _bind_params_oracle(sql: str, params: dict) -> tuple[str, dict]:
    """Oracle uses :param syntax natively."""
    return sql, params


def _bind_params_sqlserver(sql: str, params: dict) -> tuple[str, dict]:
    """Convert :param to %(param)s for pymssql."""
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

    try:
        start = time.time()
        db = get_connection(conn)
        cursor = db.cursor()

        if conn.db_type == "sqlserver":
            sql, param_values = _bind_params_sqlserver(sql, param_values)
        else:
            sql, param_values = _bind_params_oracle(sql, param_values)

        if param_values:
            cursor.execute(sql, param_values)
        else:
            cursor.execute(sql)

        columns = [desc[0].lower() if desc[0] else f"col_{i}" for i, desc in enumerate(cursor.description or [])]
        rows = [list(row) for row in cursor.fetchall()]
        elapsed = time.time() - start

        cursor.close()
        db.close()

        return QueryResult(
            query_name=query.name,
            connection_name=conn.name,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            elapsed=elapsed,
        )
    except Exception as e:
        return QueryResult(
            query_name=query.name,
            connection_name=conn.name,
            columns=[],
            rows=[],
            row_count=0,
            elapsed=0,
            success=False,
            error=str(e),
        )


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
