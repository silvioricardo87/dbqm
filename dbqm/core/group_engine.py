"""Group execution and comparison engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from dbqm.core.query_engine import QueryResult


@dataclass
class ComparisonRow:
    key_value: Any
    values: dict[str, Any]  # {query_name: value}
    status: str  # "OK", "DIFF", "ABSENT", "OK*" (normalized match)


@dataclass
class ComparisonResult:
    column: str
    rows: list[ComparisonRow]
    total_keys: int
    equal_count: int
    diff_count: int
    absent_count: int
    normalized_count: int  # OK* matches


@dataclass
class GroupResult:
    group_name: str
    query_results: dict[str, QueryResult]
    comparisons: list[ComparisonResult]
    all_match: bool
    summary_lines: list[str] = field(default_factory=list)


def run_comparison(
    results: dict[str, QueryResult],
    join_key: str,
    compare_columns: list[str],
    column_mapping: dict | None = None,
    normalize: dict | None = None,
) -> list[ComparisonResult]:
    """Compare results from multiple queries on specified columns."""
    column_mapping = column_mapping or {}
    normalize = normalize or {}

    # Index rows by join_key for each query
    indexed: dict[str, dict[Any, dict]] = {}
    for qname, result in results.items():
        indexed[qname] = {}
        key_idx = None
        for i, col in enumerate(result.columns):
            if col == join_key:
                key_idx = i
                break
        if key_idx is None:
            continue
        for row in result.rows:
            key_val = row[key_idx]
            row_dict = dict(zip(result.columns, row))
            indexed[qname][key_val] = row_dict

    # Collect all unique keys
    all_keys: set = set()
    for qname_data in indexed.values():
        all_keys.update(qname_data.keys())
    sorted_keys = sorted(all_keys, key=lambda x: (isinstance(x, str), x))

    query_names = list(results.keys())
    comparisons = []

    for col in compare_columns:
        norm_map = normalize.get(col, {})
        col_map = column_mapping.get(col, {})

        rows: list[ComparisonRow] = []
        equal_count = 0
        diff_count = 0
        absent_count = 0
        normalized_count = 0

        for key in sorted_keys:
            values = {}
            raw_values = {}
            has_absent = False

            for qname in query_names:
                mapped_col = col_map.get(qname, col) if col_map else col
                row_data = indexed.get(qname, {}).get(key)
                if row_data is None:
                    values[qname] = None
                    raw_values[qname] = None
                    has_absent = True
                else:
                    val = row_data.get(mapped_col)
                    raw_values[qname] = val
                    # Apply normalization
                    norm_val = str(val) if val is not None else ""
                    norm_val = norm_map.get(norm_val, norm_val)
                    values[qname] = norm_val

            if has_absent:
                status = "ABSENT"
                absent_count += 1
            else:
                unique_normalized = set(v for v in values.values() if v is not None)
                unique_raw = set(str(v) for v in raw_values.values() if v is not None)
                if len(unique_normalized) <= 1:
                    if len(unique_raw) <= 1:
                        status = "OK"
                        equal_count += 1
                    else:
                        status = "OK*"
                        normalized_count += 1
                else:
                    status = "DIFF"
                    diff_count += 1

            rows.append(ComparisonRow(
                key_value=key,
                values=raw_values,
                status=status,
            ))

        comparisons.append(ComparisonResult(
            column=col,
            rows=rows,
            total_keys=len(sorted_keys),
            equal_count=equal_count,
            diff_count=diff_count,
            absent_count=absent_count,
            normalized_count=normalized_count,
        ))

    return comparisons


def build_group_result(
    group_name: str,
    query_results: dict[str, QueryResult],
    join_key: str,
    compare_columns: list[str],
    column_mapping: dict | None = None,
    normalize: dict | None = None,
) -> GroupResult:
    """Build complete group comparison result."""
    comparisons = run_comparison(
        query_results, join_key, compare_columns, column_mapping, normalize
    )

    all_match = all(
        c.diff_count == 0 and c.absent_count == 0
        for c in comparisons
    )

    summary_lines = []
    for comp in comparisons:
        summary_lines.append(f"Coluna: {comp.column}")
        summary_lines.append(f"  Iguais:       {comp.equal_count}")
        if comp.normalized_count > 0:
            summary_lines.append(f"  Iguais (norm): {comp.normalized_count}")
        summary_lines.append(f"  Diferentes:   {comp.diff_count}")
        summary_lines.append(f"  Ausentes:     {comp.absent_count}")

    return GroupResult(
        group_name=group_name,
        query_results=query_results,
        comparisons=comparisons,
        all_match=all_match,
        summary_lines=summary_lines,
    )
