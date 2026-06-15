"""Export query results to CSV, JSON, or TXT."""
from __future__ import annotations

import csv
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any

from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

# Base directory override for exports. None means resolve from settings (or CWD fallback).
# Tests set this to a tmp dir to redirect output deterministically.
EXPORTS_DIR: Path | None = None

# Query exports go directly into the resolved base dir (no category subfolder).
_QUERY_CATEGORY = "consultas"

# Max length for the params portion of a filename
_MAX_PARAMS_LEN = 60
# Max length for normalized directory/label names
_MAX_LABEL_LEN = 40
# Conservative max length for the full path. Windows default MAX_PATH is 260;
# this leaves headroom for `.png`/`.html` extensions and any caller-added suffix.
_MAX_PATH_LEN = 240
# Hard floor for the filename body when truncating — keeps timestamp readable.
_MIN_FILENAME_BODY = 8


def _sanitize(name: str) -> str:
    """Sanitize a name for safe use in filenames."""
    s = name.replace(" ", "_").replace("/", "_").replace("\\", "_")
    s = re.sub(r'[<>:"|?*]', "_", s)
    return s


def _normalize_label(name: str) -> str:
    """Normalize a name for use as subdirectory: lowercase, no accents, no special chars, truncated."""
    # Remove accents (é→e, ã→a, etc.)
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = _sanitize(s).lower()
    s = re.sub(r'_+', '_', s).strip('_')
    if len(s) > _MAX_LABEL_LEN:
        s = s[:_MAX_LABEL_LEN].rstrip('_')
    return s or "export"


def _resolve_base_dir() -> Path:
    """Resolve the export base directory.

    Order: EXPORTS_DIR override (tests) → Settings.default_export_dir → CWD.
    """
    if EXPORTS_DIR is not None:
        return EXPORTS_DIR
    try:
        from dbqm.models.settings import load_settings
        configured = load_settings().default_export_dir
        if configured:
            return Path(configured)
    except Exception:
        pass
    return Path.cwd()


def _should_create_subdirs() -> bool:
    """Whether non-query categories should be nested under category/label subfolders."""
    if EXPORTS_DIR is not None:
        # Tests historically expect the nested layout when overriding EXPORTS_DIR.
        return True
    try:
        from dbqm.models.settings import load_settings
        return load_settings().create_export_subdirs
    except Exception:
        return True


def _ensure_dir(category: str, label: str) -> Path:
    """Resolve and create the target directory for an export.

    Queries (consultas) always go directly into the resolved base — no subfolder.
    Other categories nest under {category}/{label}/ when create_export_subdirs is on.
    """
    base = _resolve_base_dir()
    if category == _QUERY_CATEGORY:
        d = base
    elif _should_create_subdirs():
        d = base / category / _normalize_label(label)
    else:
        d = base
    d.mkdir(parents=True, exist_ok=True)
    return d


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _params_suffix(params: dict | None) -> str:
    """Build a compact filename suffix from query parameters.

    Truncates to _MAX_PARAMS_LEN to prevent excessively long filenames.
    Example: '_id-123_status-ativo'
    """
    if not params:
        return ""
    parts = []
    for k, v in params.items():
        safe_v = _sanitize(str(v)).replace(".", "_")
        parts.append(f"{_sanitize(k)}-{safe_v}")
    suffix = "_" + "_".join(parts)
    if len(suffix) > _MAX_PARAMS_LEN:
        suffix = suffix[:_MAX_PARAMS_LEN]
    return suffix


def _fit_path(directory: Path, filename: str) -> Path:
    """Truncate filename body if `directory / filename` would exceed _MAX_PATH_LEN.

    Preserves the extension so file-type association stays valid. If even the
    minimal filename (extension + floor body) cannot fit under the cap, returns
    the path anyway — the OS will surface the real error rather than dbqm
    silently corrupting the name.
    """
    full = directory / filename
    excess = len(str(full)) - _MAX_PATH_LEN
    if excess <= 0:
        return full
    base, dot, ext = filename.rpartition(".")
    if not dot:
        base, ext = filename, ""
        dot = ""
    target_base_len = max(len(base) - excess, _MIN_FILENAME_BODY)
    new_base = base[:target_base_len].rstrip("_.")
    if not new_base:
        new_base = base[:_MIN_FILENAME_BODY] or "export"
    return directory / f"{new_base}{dot}{ext}"


def _build_filepath(category: str, label: str, conn_name: str = "",
                    params: dict | None = None, ext: str = "txt",
                    extra: str = "") -> Path:
    """Build a standard export file path.

    Layout (after the export-dir refactor):
      - Queries: {base}/{conn}_{params}{extra}_{timestamp}.{ext}
      - Other categories (when subdirs enabled): {base}/{category}/{label}/{conn}_{params}{extra}_{timestamp}.{ext}
      - Other categories (when subdirs disabled): {base}/{conn}_{params}{extra}_{timestamp}.{ext}

    The final path is truncated if it would exceed _MAX_PATH_LEN (Windows safety).
    """
    d = _ensure_dir(category, label)
    conn_part = _sanitize(conn_name) if conn_name else ""
    filename = f"{conn_part}{_params_suffix(params)}{extra}_{_timestamp()}.{ext}"
    # Remove leading underscore if no conn_part
    filename = filename.lstrip("_")
    return _fit_path(d, filename)


# ---------------------------------------------------------------------------
# Single query exports
# ---------------------------------------------------------------------------

def export_sql_file(sql_text: str, label: str = "adhoc", params: dict | None = None) -> str:
    """Export a generated SQL text to a .sql file. Returns the file path."""
    filepath = _build_filepath("sql", label, params=params, ext="sql")
    filepath.write_text(sql_text, encoding="utf-8")
    return str(filepath)


def export_dbms_output(lines: list[str], label: str = "adhoc",
                       conn_name: str = "", params: dict | None = None) -> str:
    """Export captured DBMS_OUTPUT lines to a .txt file. Returns the file path."""
    filepath = _build_filepath("dbms_output", label, conn_name, params, "txt")
    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


def export_query_csv(result: QueryResult, table: str = "", params: dict | None = None) -> str:
    """Export a single query result to CSV. Returns the file path."""
    label = table or result.query_name
    filepath = _build_filepath("consultas", label, result.connection_name, params, "csv")
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
    return str(filepath)


def export_query_json(result: QueryResult, table: str = "", params: dict | None = None) -> str:
    """Export a single query result to JSON."""
    label = table or result.query_name
    filepath = _build_filepath("consultas", label, result.connection_name, params, "json")
    data = {
        "query": result.query_name,
        "connection": result.connection_name,
        "columns": result.columns,
        "row_count": result.row_count,
        "elapsed": round(result.elapsed, 3),
        "rows": [dict(zip(result.columns, row)) for row in result.rows],
    }
    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(filepath)


def export_query_txt(result: QueryResult, table: str = "", params: dict | None = None) -> str:
    """Export a single query result as formatted text (same as display)."""
    label = table or result.query_name
    filepath = _build_filepath("consultas", label, result.connection_name, params, "txt")

    lines = _build_query_txt_lines(result)

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


def export_individual_txt(
    result: QueryResult, sql: str = "", params: dict | None = None,
) -> str:
    """Export individual query result with SQL and parameters (mirrors screen display)."""
    filepath = _build_filepath("consultas", result.query_name, result.connection_name, params, "txt")

    lines = []

    # Parameters
    if params:
        lines.append("Parametros:")
        max_key = max(len(k) for k in params)
        for k, v in params.items():
            lines.append(f"  {k.ljust(max_key)}  =  {v}")
        lines.append("")

    # SQL
    if sql:
        lines.append("SQL:")
        lines.append("-" * 60)
        lines.append(sql.strip())
        lines.append("-" * 60)
        lines.append("")

    # Query result table + stats
    lines.extend(_build_query_txt_lines(result))

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


def _build_query_txt_lines(result: QueryResult) -> list[str]:
    """Build formatted text lines for a query result table."""
    lines = []
    lines.append(f"Consulta: {result.query_name}")
    lines.append(f"Conexao: {result.connection_name}")
    lines.append(f"Registros: {result.row_count}")
    lines.append(f"Tempo: {result.elapsed:.2f}s")
    lines.append("")

    if not result.rows:
        return lines

    # Simple table formatting
    col_widths = [len(c) for c in result.columns]
    for row in result.rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(val) if val is not None else ""))

    header = " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(result.columns))
    sep = "-+-".join("-" * w for w in col_widths)
    lines.append(header)
    lines.append(sep)
    for row in result.rows:
        line = " | ".join(str(v if v is not None else "").ljust(col_widths[i]) for i, v in enumerate(row))
        lines.append(line)

    return lines


# ---------------------------------------------------------------------------
# Group exports — pivoted (one table per key)
# ---------------------------------------------------------------------------

def _build_pivoted_data(group_result: GroupResult) -> tuple[list[str], list[str], list, dict]:
    """Build pivoted data structure for group export.

    Returns (query_names, compare_columns, all_keys, lookup).
    lookup: {(key_value, column): ComparisonRow}
    """
    query_names = list(group_result.query_results.keys())
    compare_columns = [c.column for c in group_result.comparisons]
    lookup = {}
    all_keys = []
    for comp in group_result.comparisons:
        for row in comp.rows:
            lookup[(row.key_value, comp.column)] = row
            if row.key_value not in all_keys:
                all_keys.append(row.key_value)
    return query_names, compare_columns, all_keys, lookup


def _worst_status(statuses: list[str]) -> str:
    priority = {"ABSENT": 3, "DIFF": 2, "OK*": 1, "OK": 0}
    return max(statuses, key=lambda s: priority.get(s, 0))


def _status_label(status: str) -> str:
    return {"OK": "v OK", "OK*": "v OK*", "DIFF": "! DIFF", "ABSENT": "x AUSENTE"}.get(status, status)


def export_group_csv(group_result: GroupResult, params: dict | None = None) -> str:
    """Export pivoted group comparison to CSV (one section per key)."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="csv")

    query_names, compare_columns, all_keys, lookup = _build_pivoted_data(group_result)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        if params:
            for k, v in params.items():
                f.write(f"# Parametro: {k} = {v}\n")
        f.write(f"# Grupo: {group_result.group_name}\n")
        f.write(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Resultado: {'CONSISTENTE' if group_result.all_match else 'DIVERGENTE'}\n\n")

        writer = csv.writer(f)
        header = ["chave", "consulta"] + compare_columns + ["status"]

        for key in all_keys:
            writer.writerow(header)
            for qn in query_names:
                row_data = [key, qn]
                for col in compare_columns:
                    comp_row = lookup.get((key, col))
                    val = comp_row.values.get(qn) if comp_row else None
                    row_data.append(val if val is not None else "")
                row_data.append("")
                writer.writerow(row_data)

            col_statuses = [lookup.get((key, col)).status if lookup.get((key, col)) else "ABSENT" for col in compare_columns]
            overall = _worst_status(col_statuses)
            result_row = ["", "Resultado"] + [_status_label(s) for s in col_statuses] + [_status_label(overall)]
            writer.writerow(result_row)
            f.write("\n")

    return str(filepath)


def export_group_json(group_result: GroupResult, params: dict | None = None) -> str:
    """Export pivoted group comparison to JSON."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="json")

    query_names, compare_columns, all_keys, lookup = _build_pivoted_data(group_result)

    data: dict[str, Any] = {
        "group": group_result.group_name,
        "params": params or {},
        "all_match": group_result.all_match,
        "keys": [],
    }

    for key in all_keys:
        col_statuses = []
        key_entry: dict[str, Any] = {"key": key, "queries": {}, "result": {}}

        for qn in query_names:
            qn_values = {}
            for col in compare_columns:
                comp_row = lookup.get((key, col))
                val = comp_row.values.get(qn) if comp_row else None
                qn_values[col] = val
            key_entry["queries"][qn] = qn_values

        for col in compare_columns:
            comp_row = lookup.get((key, col))
            status = comp_row.status if comp_row else "ABSENT"
            key_entry["result"][col] = status
            col_statuses.append(status)

        key_entry["result"]["overall"] = _worst_status(col_statuses)
        data["keys"].append(key_entry)

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(filepath)


def export_group_txt(group_result: GroupResult, params: dict | None = None) -> str:
    """Export pivoted group comparison as formatted text."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="txt")

    query_names, compare_columns, all_keys, lookup = _build_pivoted_data(group_result)

    lines = []
    lines.append(f"Grupo: {group_result.group_name}")
    lines.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if params:
        for k, v in params.items():
            lines.append(f"Parametro: {k} = {v}")
    lines.append(f"Resultado: {'CONSISTENTE' if group_result.all_match else 'DIVERGENTE'}")
    lines.append("")

    for key in all_keys:
        lines.append(f"chave: {key}")

        # Calculate column widths
        col_w = {"consulta": max(len("Resultado"), max(len(qn) for qn in query_names))}
        for col in compare_columns:
            col_w[col] = len(col)
            for qn in query_names:
                comp_row = lookup.get((key, col))
                val = comp_row.values.get(qn) if comp_row else None
                col_w[col] = max(col_w[col], len(str(val) if val is not None else "-"))
            # status label width
            comp_row = lookup.get((key, col))
            if comp_row:
                col_w[col] = max(col_w[col], len(_status_label(comp_row.status)))
        col_w["status"] = max(7, max(len(_status_label("ABSENT")), len("status")))

        # Header
        hdr = " | ".join([
            "consulta".ljust(col_w["consulta"]),
            *[c.ljust(col_w[c]) for c in compare_columns],
            "status".ljust(col_w["status"]),
        ])
        sep = "-+-".join([
            "-" * col_w["consulta"],
            *["-" * col_w[c] for c in compare_columns],
            "-" * col_w["status"],
        ])
        lines.append(hdr)
        lines.append(sep)

        # Query rows
        for qn in query_names:
            parts = [qn.ljust(col_w["consulta"])]
            for col in compare_columns:
                comp_row = lookup.get((key, col))
                val = comp_row.values.get(qn) if comp_row else None
                parts.append(str(val if val is not None else "-").ljust(col_w[col]))
            parts.append("".ljust(col_w["status"]))
            lines.append(" | ".join(parts))

        # Result row
        lines.append(sep)
        col_statuses = []
        parts = ["Resultado".ljust(col_w["consulta"])]
        for col in compare_columns:
            comp_row = lookup.get((key, col))
            status = comp_row.status if comp_row else "ABSENT"
            col_statuses.append(status)
            parts.append(_status_label(status).ljust(col_w[col]))
        overall = _worst_status(col_statuses)
        parts.append(_status_label(overall).ljust(col_w["status"]))
        lines.append(" | ".join(parts))
        lines.append("")

    # Summary
    for comp in group_result.comparisons:
        lines.append(f"Coluna: {comp.column}")
        lines.append(f"  Iguais:       {comp.equal_count}/{comp.total_keys}")
        if comp.normalized_count > 0:
            lines.append(f"  Normalizados: {comp.normalized_count}/{comp.total_keys}")
        lines.append(f"  Diferentes:   {comp.diff_count}/{comp.total_keys}")
        lines.append(f"  Ausentes:     {comp.absent_count}/{comp.total_keys}")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


# ---------------------------------------------------------------------------
# Group exports — flat (one section per compare column)
# ---------------------------------------------------------------------------

def _flat_status_label(status: str) -> str:
    return {"OK": "Igual", "OK*": "Igual*", "DIFF": "Diferente", "ABSENT": "Ausente"}.get(status, status)


def export_group_flat_csv(group_result: GroupResult, params: dict | None = None) -> str:
    """Export flat group comparison to CSV (one section per compare column)."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="csv", extra="_flat")

    query_names = list(group_result.query_results.keys())

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        if params:
            for k, v in params.items():
                f.write(f"# Parametro: {k} = {v}\n")
        f.write(f"# Grupo: {group_result.group_name}\n")
        f.write(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Resultado: {'CONSISTENTE' if group_result.all_match else 'DIVERGENTE'}\n\n")

        writer = csv.writer(f)
        for comp in group_result.comparisons:
            f.write(f"# Coluna: {comp.column}\n")
            header = ["chave"] + query_names + ["status"]
            writer.writerow(header)
            for row in comp.rows:
                cells = [row.key_value]
                for qn in query_names:
                    val = row.values.get(qn)
                    cells.append(val if val is not None else "")
                cells.append(_flat_status_label(row.status))
                writer.writerow(cells)
            f.write("\n")

    return str(filepath)


def export_group_flat_json(group_result: GroupResult, params: dict | None = None) -> str:
    """Export flat group comparison to JSON."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="json", extra="_flat")

    query_names = list(group_result.query_results.keys())

    data: dict[str, Any] = {
        "group": group_result.group_name,
        "params": params or {},
        "all_match": group_result.all_match,
        "columns": [],
    }

    for comp in group_result.comparisons:
        col_data: dict[str, Any] = {
            "column": comp.column,
            "summary": {
                "total": comp.total_keys,
                "equal": comp.equal_count,
                "diff": comp.diff_count,
                "absent": comp.absent_count,
                "normalized": comp.normalized_count,
            },
            "rows": [],
        }
        for row in comp.rows:
            row_entry = {"key": row.key_value, "status": _flat_status_label(row.status)}
            for qn in query_names:
                row_entry[qn] = row.values.get(qn)
            col_data["rows"].append(row_entry)
        data["columns"].append(col_data)

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(filepath)


def export_group_flat_txt(group_result: GroupResult, params: dict | None = None) -> str:
    """Export flat group comparison as formatted text."""
    filepath = _build_filepath("grupos", group_result.group_name, params=params, ext="txt", extra="_flat")

    query_names = list(group_result.query_results.keys())

    lines = []
    lines.append(f"Grupo: {group_result.group_name}")
    lines.append(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if params:
        for k, v in params.items():
            lines.append(f"Parametro: {k} = {v}")
    lines.append(f"Resultado: {'CONSISTENTE' if group_result.all_match else 'DIVERGENTE'}")
    lines.append("")

    for comp in group_result.comparisons:
        lines.append(f"Coluna: {comp.column}")

        # Calculate column widths
        col_w = {"chave": len("chave")}
        for row in comp.rows:
            col_w["chave"] = max(col_w["chave"], len(str(row.key_value)))
        for qn in query_names:
            col_w[qn] = len(qn)
            for row in comp.rows:
                val = row.values.get(qn)
                col_w[qn] = max(col_w[qn], len(str(val) if val is not None else "-"))
        col_w["status"] = max(len("status"), len("Diferente"))

        # Header
        hdr = " | ".join([
            "chave".ljust(col_w["chave"]),
            *[qn.ljust(col_w[qn]) for qn in query_names],
            "status".ljust(col_w["status"]),
        ])
        sep = "-+-".join([
            "-" * col_w["chave"],
            *["-" * col_w[qn] for qn in query_names],
            "-" * col_w["status"],
        ])
        lines.append(hdr)
        lines.append(sep)

        for row in comp.rows:
            parts = [str(row.key_value).ljust(col_w["chave"])]
            for qn in query_names:
                val = row.values.get(qn)
                parts.append(str(val if val is not None else "-").ljust(col_w[qn]))
            parts.append(_flat_status_label(row.status).ljust(col_w["status"]))
            lines.append(" | ".join(parts))
        lines.append("")

        # Summary
        lines.append(f"  Iguais: {comp.equal_count}/{comp.total_keys}")
        if comp.normalized_count > 0:
            lines.append(f"  Normalizados: {comp.normalized_count}/{comp.total_keys}")
        lines.append(f"  Diferentes: {comp.diff_count}/{comp.total_keys}")
        lines.append(f"  Ausentes: {comp.absent_count}/{comp.total_keys}")
        lines.append("")

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)
