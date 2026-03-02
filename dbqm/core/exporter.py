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


def export_group_csv(group_result: GroupResult, params: dict | None = None) -> str:
    """Export group comparison to CSV."""
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.csv"
    filepath = d / filename

    query_names = list(group_result.query_results.keys())

    lines = []
    if params:
        for k, v in params.items():
            lines.append(f"# Parametro: {k} = {v}")
    lines.append(f"# Grupo: {group_result.group_name}")
    lines.append(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"# Resultado: {'CONSISTENTE' if group_result.all_match else 'DIVERGENTE'}")
    lines.append("")

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")

        for comp in group_result.comparisons:
            f.write(f"\n# Comparacao: {comp.column}\n")
            writer = csv.writer(f)
            header = ["chave"] + [f"{qn}_{comp.column}" for qn in query_names] + ["status"]
            writer.writerow(header)
            for row in comp.rows:
                csv_row = [row.key_value]
                for qn in query_names:
                    val = row.values.get(qn)
                    csv_row.append(val if val is not None else "")
                csv_row.append(row.status)
                writer.writerow(csv_row)

    return str(filepath)


def export_group_json(group_result: GroupResult, params: dict | None = None) -> str:
    """Export group comparison to JSON."""
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.json"
    filepath = d / filename

    query_names = list(group_result.query_results.keys())
    data = {
        "group": group_result.group_name,
        "params": params or {},
        "all_match": group_result.all_match,
        "comparisons": [],
    }
    for comp in group_result.comparisons:
        comp_data = {
            "column": comp.column,
            "total_keys": comp.total_keys,
            "equal": comp.equal_count,
            "different": comp.diff_count,
            "absent": comp.absent_count,
            "normalized": comp.normalized_count,
            "rows": [],
        }
        for row in comp.rows:
            comp_data["rows"].append({
                "key": row.key_value,
                "values": {qn: row.values.get(qn) for qn in query_names},
                "status": row.status,
            })
        data["comparisons"].append(comp_data)

    filepath.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return str(filepath)


def export_group_txt(group_result: GroupResult, params: dict | None = None) -> str:
    """Export group comparison as formatted text."""
    d = _ensure_exports_dir()
    filename = f"grupo_{_sanitize(group_result.group_name)}_{_timestamp()}.txt"
    filepath = d / filename

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
        lines.append(f"Comparacao: {comp.column}")
        lines.append(f"  Iguais: {comp.equal_count}  Diferentes: {comp.diff_count}  Ausentes: {comp.absent_count}")
        if comp.normalized_count:
            lines.append(f"  Iguais (normalizados): {comp.normalized_count}")
        lines.append("")

        col_widths = {"chave": 6}
        for qn in query_names:
            col_widths[qn] = len(qn)
        col_widths["status"] = 7

        for row in comp.rows:
            col_widths["chave"] = max(col_widths["chave"], len(str(row.key_value)))
            for qn in query_names:
                val = row.values.get(qn, "")
                col_widths[qn] = max(col_widths[qn], len(str(val) if val is not None else "-"))
            col_widths["status"] = max(col_widths["status"], len(row.status) + 2)

        header_parts = [
            "chave".ljust(col_widths["chave"]),
            *[qn.ljust(col_widths[qn]) for qn in query_names],
            "status".ljust(col_widths["status"]),
        ]
        lines.append(" | ".join(header_parts))
        lines.append("-+-".join("-" * col_widths[k] for k in ["chave"] + query_names + ["status"]))

        for row in comp.rows:
            parts = [str(row.key_value).ljust(col_widths["chave"])]
            for qn in query_names:
                val = row.values.get(qn)
                parts.append(str(val if val is not None else "-").ljust(col_widths[qn]))
            status_icon = {"OK": "v OK", "OK*": "v OK*", "DIFF": "! DIFF", "ABSENT": "x AUSENTE"}.get(row.status, row.status)
            parts.append(status_icon.ljust(col_widths["status"]))
            lines.append(" | ".join(parts))

        lines.append("")

    for sl in group_result.summary_lines:
        lines.append(sl)

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)
