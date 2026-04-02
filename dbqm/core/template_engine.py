"""Template rendering engine for grouped query results."""
from __future__ import annotations

import re
from typing import Any

from dbqm.core.group_engine import GroupResult


# Regex to find {{field_name}} placeholders
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def extract_placeholders(content: str) -> list[str]:
    """Extract all unique {{field}} placeholder names from template content."""
    return list(dict.fromkeys(PLACEHOLDER_RE.findall(content)))


def resolve_auto_fields(
    group_result: GroupResult,
    param_values: dict[str, str],
    template_fields: dict[str, str],
) -> dict[str, str]:
    """Resolve template fields that have auto-source expressions.

    Source expressions:
      - "param:PARAM_NAME"           -> parameter value
      - "query:QUERY_NAME:_count"    -> row count
      - "query:QUERY_NAME:COL_NAME"  -> first row column value
      - "query:QUERY_NAME:COL_NAME:N" -> Nth row column value (0-indexed)
      - "literal:text"               -> static text

    Returns dict of {field_name: resolved_value} for fields that were resolved.
    """
    resolved: dict[str, str] = {}

    for field_name, source in template_fields.items():
        if not source:
            continue

        value = _resolve_source(source, group_result, param_values)
        if value is not None:
            resolved[field_name] = value

    return resolved


def _resolve_source(
    source: str,
    group_result: GroupResult,
    param_values: dict[str, str],
) -> str | None:
    """Resolve a single source expression to a string value."""
    parts = source.split(":", maxsplit=1)
    if len(parts) < 2:
        return None

    source_type = parts[0]
    source_rest = parts[1]

    if source_type == "literal":
        return source_rest

    if source_type == "param":
        return param_values.get(source_rest, "")

    if source_type == "query":
        return _resolve_query_source(source_rest, group_result)

    return None


def _resolve_query_source(source_rest: str, group_result: GroupResult) -> str | None:
    """Resolve a query:... source expression."""
    parts = source_rest.split(":")
    if len(parts) < 2:
        return None

    query_name = parts[0]
    field = parts[1]

    qr = group_result.query_results.get(query_name)
    if qr is None:
        return None

    if field == "_count":
        return str(qr.row_count)

    if field == "_count_label":
        n = qr.row_count
        return f"{n} registro{'s' if n != 1 else ''}"

    if field == "_status":
        return "OK" if qr.row_count > 0 else "VAZIO"

    if field == "_name":
        return query_name

    # Column value from specific row
    col_idx = None
    for i, col in enumerate(qr.columns):
        if col == field:
            col_idx = i
            break

    if col_idx is None:
        return None

    row_idx = int(parts[2]) if len(parts) > 2 else 0
    if row_idx >= len(qr.rows):
        return ""

    value = qr.rows[row_idx][col_idx]
    return str(value) if value is not None else ""


def get_input_fields(
    placeholders: list[str],
    resolved: dict[str, str],
) -> list[str]:
    """Return placeholder names that need user input (not auto-resolved)."""
    return [p for p in placeholders if p not in resolved]


def render_template(
    content: str,
    values: dict[str, str],
) -> str:
    """Render template content by replacing {{field}} placeholders with values."""
    def _replace(match: re.Match) -> str:
        field_name = match.group(1)
        return values.get(field_name, match.group(0))

    return PLACEHOLDER_RE.sub(_replace, content)
