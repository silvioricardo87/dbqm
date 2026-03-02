"""Export query results to CSV, JSON, or TXT."""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult

EXPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "exports"


def _ensure_exports_dir() -> Path:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    return EXPORTS_DIR


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _sanitize(name: str) -> str:
    return name.replace(" ", "_").replace("/", "_").replace("\\", "_")


def export_query_csv(result: QueryResult, table: str = "") -> str:
    """Export a single query result to CSV. Returns the file path."""
    d = _ensure_exports_dir()
    table_part = _sanitize(table) if table else "query"
    filename = f"{_sanitize(result.connection_name)}_{table_part}_{_timestamp()}.csv"
    filepath = d / filename
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(result.columns)
        writer.writerows(result.rows)
    return str(filepath)


def export_query_json(result: QueryResult, table: str = "") -> str:
    """Export a single query result to JSON."""
    d = _ensure_exports_dir()
    table_part = _sanitize(table) if table else "query"
    filename = f"{_sanitize(result.connection_name)}_{table_part}_{_timestamp()}.json"
    filepath = d / filename
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


def export_query_txt(result: QueryResult, table: str = "") -> str:
    """Export a single query result as formatted text (same as display)."""
    d = _ensure_exports_dir()
    table_part = _sanitize(table) if table else "query"
    filename = f"{_sanitize(result.connection_name)}_{table_part}_{_timestamp()}.txt"
    filepath = d / filename

    lines = []
    lines.append(f"Consulta: {result.query_name}")
    lines.append(f"Conexao: {result.connection_name}")
    lines.append(f"Registros: {result.row_count}")
    lines.append(f"Tempo: {result.elapsed:.2f}s")
    lines.append("")

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

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


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
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.csv"
    filepath = d / filename

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
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.json"
    filepath = d / filename

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
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.txt"
    filepath = d / filename

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
