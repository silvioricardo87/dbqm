"""Group execution and comparison engine."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from dbqm.core.query_engine import AdhocResult, QueryResult
from dbqm.core.read_only import ReadOnlyViolation
from dbqm.models.connection import Connection


@dataclass
class ComparisonRow:
    key_value: Any
    values: dict[str, Any]  # {query_name: value}
    status: str  # "OK", "DIFF", "ABSENT", "OK*" (normalized match)

    def to_dict(self) -> dict[str, Any]:
        """Wire shape."""
        return {
            "key_value": self.key_value,
            "values": dict(self.values),
            "status": self.status,
        }


@dataclass
class ComparisonResult:
    column: str
    rows: list[ComparisonRow]
    total_keys: int
    equal_count: int
    diff_count: int
    absent_count: int
    normalized_count: int  # OK* matches
    #: {query_name: rows dropped because their key value repeated}. Empty
    #: when every key was unique, which is the case worth saying nothing
    #: about. The same map on every column: the index is built once, before
    #: any column is compared.
    duplicate_rows: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Wire shape. Nested dataclasses serialise through their own to_dict."""
        return {
            "column": self.column,
            "rows": [r.to_dict() for r in self.rows],
            "total_keys": self.total_keys,
            "equal_count": self.equal_count,
            "diff_count": self.diff_count,
            "absent_count": self.absent_count,
            "normalized_count": self.normalized_count,
            "duplicate_rows": dict(self.duplicate_rows),
        }


@dataclass
class GroupResult:
    group_name: str
    query_results: Mapping[str, ResultLike]
    comparisons: list[ComparisonResult]
    all_match: bool
    summary_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Wire shape. Nested dataclasses serialise through their own
        to_dict. `summary_lines` does not travel here: it is Portuguese
        display prose (`"  Iguais:       3"`), and every number in it is
        already in `comparisons[*].*_count` — presentation, not data."""
        return {
            "group_name": self.group_name,
            "query_results": {
                name: qr.to_dict() for name, qr in self.query_results.items()
            },
            "comparisons": [c.to_dict() for c in self.comparisons],
            "all_match": self.all_match,
        }


#: {column: {query_name: the column that query calls it}}
ColumnMapping = dict[str, dict[str, str]]
#: {column: {raw value: the value it counts as}}
Normalization = dict[str, dict[str, str]]


class NoComparableColumns(Exception):
    """The results have no column in common, so there is nothing to compare."""


class ResultLike(Protocol):
    """What the comparison actually reads. `run_comparison` has always been
    annotated `QueryResult` while the Multi-Exec screen passed it
    `AdhocResult`; naming the real requirement retires that mismatch for new
    code without touching the old signature."""
    columns: list[str]
    rows: list[list[Any]]
    row_count: int

    def to_dict(self) -> dict[str, Any]: ...


def derive_comparison_columns(
    results: Mapping[str, ResultLike],
) -> tuple[str, list[str]]:
    """Derive the join key and compare columns from the columns common to
    every result.

    The first result's column order wins -- not sorted, not any other
    result's order. The join key is the first common column, the compare
    columns are the rest. Raises `NoComparableColumns` when no column is
    common to every result, or when there is no result to derive from at all.
    """
    if not results:
        raise NoComparableColumns(
            "Consultas nao retornaram colunas comparaveis."
        )
    first = next(iter(results))
    base_cols = list(results[first].columns)
    common = [
        c for c in base_cols
        if all(c in r.columns for r in results.values())
    ]
    if not common:
        raise NoComparableColumns(
            "Consultas nao retornaram colunas comparaveis."
        )
    return common[0], common[1:]


def build_adhoc_group_result(
    results: Mapping[str, ResultLike],
    join_key: str = "",
    compare_columns: list[str] | None = None,
) -> GroupResult:
    """Build a `GroupResult` for an ad-hoc, group-name-less comparison.

    When `join_key` is not given, both it and `compare_columns` are derived
    from the columns common to every result (see `derive_comparison_columns`).
    """
    if not join_key:
        join_key, compare_columns = derive_comparison_columns(results)
    elif compare_columns is None:
        compare_columns = []

    comparisons = run_comparison(results, join_key, compare_columns)
    all_match = all(
        c.diff_count == 0 and c.absent_count == 0 for c in comparisons
    )
    return GroupResult(
        group_name="(ad-hoc)",
        query_results=results,
        comparisons=comparisons,
        all_match=all_match,
    )


def execute_across(
    sql: str,
    conns: list[tuple[str, Connection | None]],
    param_values: dict[str, str],
    on_progress: Callable[[str], None] | None = None,
    on_result: Callable[[str, AdhocResult], None] | None = None,
    on_missing: Callable[[str], None] | None = None,
) -> dict[str, AdhocResult]:
    """Run the same SQL on each resolved connection, in order.

    `conns` is a list of `(name, connection)` pairs, already resolved by the
    caller -- core does not look connections up itself. `dbqm/cli/deps.py`
    exists precisely so the CLI's connection lookup can be rebound in tests;
    a lookup done here would route around that seam. A pair whose connection
    is `None` fires `on_missing(name)`, in sequence with the pairs around it,
    and contributes **no entry** to the returned dict -- it was never run,
    so there is nothing to report. A pair that *did* run, successfully or
    not, always gets an entry; Task 3 tells the two apart by entry
    membership (`not_found`) versus `AdhocResult.error_kind` (`connection_failed`
    vs `sql_error`).

    Decides nothing about what a failure means -- the TUI carries on so a
    dead connection does not discard the comparison on screen, the CLI stops
    because a comparison over a subset answers a different question. A core
    that picked one policy would force the other to work around it.

    A raised exception becomes an unsuccessful AdhocResult, so one
    unreachable host cannot end the loop. `error_kind` says which: a
    `ReadOnlyViolation` is caught first and tagged `"read_only"` -- the
    guard refused to send the statement at all, which is a different fact
    from the database never answering, and conflating the two would make a
    caller report a healthy connection as failed. Anything else becomes
    `error_kind="connection"`. Deciding what those tokens *mean* -- which
    exit code, which message -- stays the caller's job; this only records
    what happened.

    `on_progress`, `on_result` and `on_missing` each fire once per pair, in
    the same sequential order as `conns` -- a caller that wants to react
    per-connection (notify, log, stop) does not have to wait for every other
    connection to finish first.
    """
    from dbqm.core.query_engine import execute_adhoc

    results: dict[str, AdhocResult] = {}
    for name, conn in conns:
        if conn is None:
            if on_missing is not None:
                on_missing(name)
            continue

        if on_progress is not None:
            on_progress(name)

        try:
            res = execute_adhoc(sql, conn, param_values)
        except ReadOnlyViolation as e:
            res = AdhocResult(
                sql_type="",
                connection_name=name,
                sql=sql,
                db_type=conn.db_type,
                success=False,
                error=str(e),
                error_kind="read_only",
            )
        except Exception as e:
            res = AdhocResult(
                sql_type="",
                connection_name=name,
                sql=sql,
                db_type=conn.db_type,
                success=False,
                error=str(e),
                error_kind="connection",
            )
        else:
            # DML without auto_commit returns (AdhocResult, db_connection).
            if isinstance(res, tuple):
                res = res[0]

        results[name] = res
        if on_result is not None:
            on_result(name, res)

    return results


def run_comparison(
    results: Mapping[str, ResultLike],
    join_key: str,
    compare_columns: list[str],
    column_mapping: ColumnMapping | None = None,
    normalize: Normalization | None = None,
) -> list[ComparisonResult]:
    """Compare results from multiple queries on specified columns."""
    column_mapping = column_mapping or {}
    normalize = normalize or {}

    # Index rows by join_key for each query
    indexed: dict[str, dict[Any, dict[str, Any]]] = {}
    # How many rows each side lost to a key value it had already seen. The
    # index keeps the last row under a repeated key, so without this the
    # comparison answers about one row and says nothing about the other --
    # `all_match: true` over data it never told apart. Counted while
    # indexing, reported by every caller.
    duplicates: dict[str, int] = {}
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
            row_dict = dict(zip(result.columns, row, strict=True))
            if key_val in indexed[qname]:
                duplicates[qname] = duplicates.get(qname, 0) + 1
            indexed[qname][key_val] = row_dict

    # Collect all unique keys
    all_keys: set[Any] = set()
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
            values: dict[str, Any] = {}
            raw_values: dict[str, Any] = {}
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
                unique_normalized = {v for v in values.values() if v is not None}
                unique_raw = {str(v) for v in raw_values.values() if v is not None}
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
            duplicate_rows=dict(duplicates),
        ))

    return comparisons


def build_group_result(
    group_name: str,
    query_results: dict[str, QueryResult],
    join_key: str,
    compare_columns: list[str],
    column_mapping: ColumnMapping | None = None,
    normalize: Normalization | None = None,
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
