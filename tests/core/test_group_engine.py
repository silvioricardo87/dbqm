"""Tests for group comparison engine."""
import pytest
from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import run_comparison, build_group_result


def _make_qr(name, conn, columns, rows):
    return QueryResult(
        query_name=name, connection_name=conn,
        columns=columns, rows=rows,
        row_count=len(rows), elapsed=0.1,
    )


class TestRunComparison:
    def test_all_equal(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "val"], [[1, "a"], [2, "b"]]),
            "q2": _make_qr("q2", "c2", ["id", "val"], [[1, "a"], [2, "b"]]),
        }
        comps = run_comparison(results, "id", ["val"])
        assert len(comps) == 1
        assert comps[0].equal_count == 2
        assert comps[0].diff_count == 0
        assert comps[0].absent_count == 0

    def test_diff_detected(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "val"], [[1, "a"]]),
            "q2": _make_qr("q2", "c2", ["id", "val"], [[1, "b"]]),
        }
        comps = run_comparison(results, "id", ["val"])
        assert comps[0].diff_count == 1
        assert comps[0].rows[0].status == "DIFF"

    def test_absent_detected(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "val"], [[1, "a"], [2, "b"]]),
            "q2": _make_qr("q2", "c2", ["id", "val"], [[1, "a"]]),
        }
        comps = run_comparison(results, "id", ["val"])
        assert comps[0].absent_count == 1

    def test_normalization(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "status"], [[1, "paga"]]),
            "q2": _make_qr("q2", "c2", ["id", "status"], [[1, "pago"]]),
        }
        comps = run_comparison(results, "id", ["status"], normalize={"status": {"paga": "pago"}})
        assert comps[0].normalized_count == 1
        assert comps[0].rows[0].status == "OK*"

    def test_column_mapping(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "estado"], [[1, "active"]]),
            "q2": _make_qr("q2", "c2", ["id", "status"], [[1, "active"]]),
        }
        comps = run_comparison(results, "id", ["estado"],
                               column_mapping={"estado": {"q2": "status"}})
        assert comps[0].equal_count == 1

    def test_missing_join_key(self):
        results = {
            "q1": _make_qr("q1", "c1", ["name"], [[" Alice"]]),
        }
        comps = run_comparison(results, "id", ["name"])
        assert comps[0].total_keys == 0


class TestBuildGroupResult:
    def test_all_match(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "val"], [[1, "x"]]),
            "q2": _make_qr("q2", "c2", ["id", "val"], [[1, "x"]]),
        }
        gr = build_group_result("g", results, "id", ["val"])
        assert gr.all_match is True
        assert gr.group_name == "g"
        assert len(gr.summary_lines) > 0

    def test_not_match(self):
        results = {
            "q1": _make_qr("q1", "c1", ["id", "val"], [[1, "x"]]),
            "q2": _make_qr("q2", "c2", ["id", "val"], [[1, "y"]]),
        }
        gr = build_group_result("g", results, "id", ["val"])
        assert gr.all_match is False
