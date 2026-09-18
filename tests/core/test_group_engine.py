"""Tests for group comparison engine."""
from dataclasses import dataclass, field
from typing import Any

import pytest
from dbqm.core.query_engine import AdhocResult, QueryResult
from dbqm.core.group_engine import (
    NoComparableColumns,
    build_adhoc_group_result,
    build_group_result,
    derive_comparison_columns,
    duplicate_key_warnings,
    execute_across,
    run_comparison,
)
from dbqm.models.connection import Connection


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


@dataclass
class _Res:
    """Stands in for AdhocResult/QueryResult: the three attributes the
    comparison actually reads."""
    columns: list[str]
    rows: list[list[Any]] = field(default_factory=list)
    success: bool = True


class TestDeriveComparisonColumns:
    def test_identical_columns_give_the_first_as_key_and_the_rest_to_compare(self):
        r = {"a": _Res(["ID", "NOME", "VALOR"]), "b": _Res(["ID", "NOME", "VALOR"])}
        assert derive_comparison_columns(r) == ("ID", ["NOME", "VALOR"])

    def test_only_the_columns_every_result_has_are_used(self):
        """A column present in one connection and not another cannot be
        compared -- it is absent, not different."""
        r = {"a": _Res(["ID", "NOME", "EXTRA"]), "b": _Res(["ID", "NOME"])}
        assert derive_comparison_columns(r) == ("ID", ["NOME"])

    def test_the_first_results_column_order_wins(self):
        """Not sorted, not the second connection's order -- the order the
        caller saw first, which is the order they wrote the SELECT in."""
        r = {"a": _Res(["NOME", "ID"]), "b": _Res(["ID", "NOME"])}
        assert derive_comparison_columns(r) == ("NOME", ["ID"])

    def test_disjoint_columns_raise_rather_than_guess(self):
        r = {"a": _Res(["ID"]), "b": _Res(["CODIGO"])}
        with pytest.raises(NoComparableColumns):
            derive_comparison_columns(r)

    def test_one_common_column_compares_nothing_but_still_has_a_key(self):
        """Degenerate but legal: the keys line up and there is nothing to
        compare. It must not raise."""
        r = {"a": _Res(["ID", "X"]), "b": _Res(["ID", "Y"])}
        assert derive_comparison_columns(r) == ("ID", [])

    def test_a_single_result_is_comparable_with_itself(self):
        """core does not enforce a minimum -- that is the CLI's rule, and
        core must not decide it."""
        r = {"a": _Res(["ID", "NOME"])}
        assert derive_comparison_columns(r) == ("ID", ["NOME"])

    def test_no_results_raises_rather_than_crashing_on_next_iter(self):
        """`next(iter({}))` is a StopIteration, not a comparison error -- an
        empty dict must raise the same NoComparableColumns as disjoint
        columns, not leak an unrelated exception to the caller."""
        with pytest.raises(NoComparableColumns):
            derive_comparison_columns({})


class TestBuildAdhocGroupResult:
    def test_derives_when_not_told(self):
        r = {"a": _Res(["ID", "N"], [[1, "x"]]), "b": _Res(["ID", "N"], [[1, "x"]])}
        gr = build_adhoc_group_result(r)
        assert gr.group_name == "(ad-hoc)"
        assert gr.all_match is True
        assert [c.column for c in gr.comparisons] == ["N"]

    def test_honours_an_explicit_key(self):
        r = {"a": _Res(["ID", "N"], [[1, "x"]]), "b": _Res(["ID", "N"], [[2, "x"]])}
        gr = build_adhoc_group_result(r, join_key="N", compare_columns=["ID"])
        assert [c.column for c in gr.comparisons] == ["ID"]
        # Both rows join on N="x" and their IDs (1 vs 2) differ under that
        # join -- pins that the explicit key actually joined the rows,
        # rather than silently matching nothing.
        assert gr.all_match is False

    def test_a_difference_is_reported_as_one(self):
        r = {"a": _Res(["ID", "N"], [[1, "x"]]), "b": _Res(["ID", "N"], [[1, "y"]])}
        assert build_adhoc_group_result(r).all_match is False


def _make_conn(name):
    return Connection(name=name, db_type="oracle", user="", password="")


def _resolved(*names):
    """`(name, Connection)` pairs, all resolved -- the shape execute_across
    expects when the caller found every connection."""
    return [(n, _make_conn(n)) for n in names]


class TestExecuteAcross:
    def test_a_raised_exception_becomes_a_connection_failure_and_the_rest_still_run(
        self, monkeypatch
    ):
        calls: list[str] = []

        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            calls.append(conn.name)
            if conn.name == "bad":
                raise RuntimeError("host unreachable")
            return AdhocResult(
                sql_type="SELECT", connection_name=conn.name,
                columns=["ID"], rows=[[1]],
            )

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        results = execute_across("SELECT 1", _resolved("bad", "good"), {})

        assert calls == ["bad", "good"]
        assert results["bad"].success is False
        assert results["bad"].error_kind == "connection"
        assert results["good"].success is True

    def test_a_read_only_violation_is_tagged_distinctly_from_a_connection_failure(
        self, monkeypatch
    ):
        """`ReadOnlyViolation` is a `RuntimeError` (the same base the generic
        `except Exception` below it would also catch), and `check_read_only`
        raises it before any connection attempt -- the guard refused to send
        the statement, which is not the same fact as the database never
        answering. Caught first and tagged its own `error_kind` so a caller
        does not report a healthy, refused-on-purpose connection as failed."""
        from dbqm.core.read_only import ReadOnlyViolation

        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            if conn.name == "prod":
                raise ReadOnlyViolation(
                    "Conexao 'prod' e somente leitura. Use --force-write para "
                    "enviar assim mesmo."
                )
            return AdhocResult(
                sql_type="SELECT", connection_name=conn.name,
                columns=["ID"], rows=[[1]],
            )

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        results = execute_across("DELETE FROM t", _resolved("prod", "homolog"), {})

        assert results["prod"].success is False
        assert results["prod"].error_kind == "read_only"
        assert results["homolog"].success is True

    def test_an_already_unsuccessful_result_keeps_its_own_error_kind(self, monkeypatch):
        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            return AdhocResult(
                sql_type="SELECT", connection_name=conn.name,
                success=False, error="ORA-00904: invalid identifier",
                error_kind="statement",
            )

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        results = execute_across("SELECT bogus FROM t", _resolved("c1"), {})
        assert results["c1"].success is False
        assert results["c1"].error_kind == "statement"

    def test_a_dml_tuple_result_is_unpacked(self, monkeypatch):
        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            res = AdhocResult(
                sql_type="UPDATE", connection_name=conn.name, rows_affected=1
            )
            return res, object()  # (AdhocResult, db_connection)

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        results = execute_across("UPDATE t SET x = 1", _resolved("c1"), {})
        assert isinstance(results["c1"], AdhocResult)
        assert results["c1"].rows_affected == 1

    def test_on_result_fires_once_per_connection_in_order_including_failures(
        self, monkeypatch
    ):
        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            if conn.name == "bad":
                raise RuntimeError("boom")
            return AdhocResult(sql_type="SELECT", connection_name=conn.name)

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        seen: list[tuple[str, bool]] = []
        execute_across(
            "SELECT 1",
            _resolved("a", "bad", "b"),
            {},
            on_result=lambda name, res: seen.append((name, res.success)),
        )
        assert seen == [("a", True), ("bad", False), ("b", True)]

    def test_a_missing_connection_gets_no_entry_but_fires_on_missing_in_order(
        self, monkeypatch
    ):
        """A `None` connection is never executed -- it must not appear in the
        returned dict at all (there is no result to report), and on_missing
        must fire in the same sequence as on_progress/on_result for the
        connections around it, not before or after them all."""
        def fake_execute_adhoc(sql, conn, param_values, auto_commit=False, capture_output=False):
            return AdhocResult(sql_type="SELECT", connection_name=conn.name)

        monkeypatch.setattr("dbqm.core.query_engine.execute_adhoc", fake_execute_adhoc)

        events: list[tuple[str, str]] = []
        conns: list[tuple[str, Connection | None]] = [
            ("a", _make_conn("a")),
            ("ghost", None),
            ("b", _make_conn("b")),
        ]
        results = execute_across(
            "SELECT 1",
            conns,
            {},
            on_progress=lambda name: events.append(("progress", name)),
            on_result=lambda name, res: events.append(("result", name)),
            on_missing=lambda name: events.append(("missing", name)),
        )

        assert "ghost" not in results
        assert set(results) == {"a", "b"}
        assert events == [
            ("progress", "a"), ("result", "a"),
            ("missing", "ghost"),
            ("progress", "b"), ("result", "b"),
        ]


class TestDuplicateKeyValues:
    """Two rows sharing a key value on the same side used to collapse into
    one silently: the index keeps the last, and the comparison answered
    about it as though the other had never existed."""

    @staticmethod
    def _result(rows):
        return QueryResult(
            query_name="q", connection_name="c",
            columns=["id", "valor"], rows=rows, row_count=len(rows), elapsed=0.0,
        )

    def test_rows_lost_to_a_repeated_key_are_counted_per_side(self):
        resultados = {
            "a": self._result([[1, "x"], [1, "y"], [2, "z"]]),
            "b": self._result([[1, "y"], [2, "z"]]),
        }
        comparacoes = run_comparison(resultados, "id", ["valor"])
        assert comparacoes[0].duplicate_rows == {"a": 1}
        assert comparacoes[0].total_keys == 2

    def test_a_unique_key_says_nothing(self):
        """An empty map is the case worth no words at all -- every caller
        renders a warning per entry."""
        resultados = {
            "a": self._result([[1, "x"], [2, "y"]]),
            "b": self._result([[1, "x"], [2, "y"]]),
        }
        comparacoes = run_comparison(resultados, "id", ["valor"])
        assert comparacoes[0].duplicate_rows == {}

    def test_the_count_is_rows_dropped_not_keys_repeated(self):
        """Three rows under one key lose two, not one."""
        resultados = {
            "a": self._result([[1, "x"], [1, "y"], [1, "z"]]),
            "b": self._result([[1, "z"]]),
        }
        comparacoes = run_comparison(resultados, "id", ["valor"])
        assert comparacoes[0].duplicate_rows == {"a": 2}

    def test_every_column_carries_the_same_map(self):
        """The index is built once, before any column is compared, so a
        caller may read the first comparison and answer for all of them."""
        resultado = QueryResult(
            query_name="q", connection_name="c",
            columns=["id", "a", "b"], rows=[[1, "x", "x"], [1, "y", "y"]],
            row_count=2, elapsed=0.0,
        )
        comparacoes = run_comparison({"um": resultado}, "id", ["a", "b"])
        assert [c.duplicate_rows for c in comparacoes] == [{"um": 1}, {"um": 1}]

    def test_it_travels_on_the_wire(self):
        resultados = {"a": self._result([[1, "x"], [1, "y"]])}
        comparacao = run_comparison(resultados, "id", ["valor"])[0]
        assert comparacao.to_dict()["duplicate_rows"] == {"a": 1}


class TestDuplicateKeyWarnings:
    """One wording, read by the CLI and by both comparison screens."""

    @staticmethod
    def _group_result(rows_a, rows_b, join_key="id"):
        def qr(nome, linhas):
            return QueryResult(
                query_name=nome, connection_name=nome,
                columns=["id", "valor"], rows=linhas, row_count=len(linhas),
                elapsed=0.0,
            )
        return build_adhoc_group_result(
            {"a": qr("a", rows_a), "b": qr("b", rows_b)},
            join_key=join_key, compare_columns=["valor"],
        )

    def test_one_line_per_side_that_lost_rows(self):
        resultado = self._group_result(
            [[1, "x"], [1, "y"], [2, "z"]], [[1, "y"], [1, "w"], [2, "z"]],
        )
        assert duplicate_key_warnings(resultado) == [
            "Key 'id' has repeated values in 'a': 1 row(s) left out of the comparison.",
            "Key 'id' has repeated values in 'b': 1 row(s) left out of the comparison.",
        ]

    def test_a_unique_key_says_nothing(self):
        resultado = self._group_result([[1, "x"]], [[1, "x"]])
        assert duplicate_key_warnings(resultado) == []

    def test_it_names_the_key_the_comparison_actually_used(self):
        """An ad-hoc comparison derives its key; the result carries it now,
        so the warning names the real column instead of a caller\'s guess."""
        resultado = self._group_result([[1, "x"], [1, "y"]], [[1, "x"]])
        assert resultado.join_key == "id"
        assert "Key 'id'" in duplicate_key_warnings(resultado)[0]

    def test_no_comparison_at_all_warns_about_nothing(self):
        """A group with nothing to compare produces no `ComparisonResult`,
        and the counts live on those."""
        resultado = self._group_result([[1, "x"], [1, "y"]], [[1, "x"]])
        resultado.comparisons = []
        assert duplicate_key_warnings(resultado) == []
