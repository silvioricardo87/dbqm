"""The guard that makes a connection query-only.

It sits at classification, before the statement is sent -- never "send it and
skip the commit". Measured: no driver sets autocommit and nothing persists
without an explicit `.commit()`, which makes refusing to commit look
sufficient. It is not: a stored routine can COMMIT internally and Oracle DDL
commits itself, and both bypass the commit gate entirely.
"""
import pytest

from dbqm.core.read_only import ReadOnlyViolation, check_read_only
from dbqm.models.connection import Connection


def _conn(read_only=True):
    return Connection(name="alvo", db_type="postgresql", user="u",
                      password="", read_only=read_only)


class TestWhatIsAllowed:
    def test_a_select_passes(self):
        check_read_only("SELECT 1 FROM dual", _conn())

    def test_an_explain_passes(self):
        check_read_only("EXPLAIN PLAN FOR SELECT 1 FROM dual", _conn())

    def test_a_cte_select_passes(self):
        check_read_only("WITH x AS (SELECT 1) SELECT * FROM x", _conn())

    def test_a_select_for_update_passes(self):
        """It takes locks but writes no data. Allowed, deliberately."""
        check_read_only("SELECT * FROM t FOR UPDATE", _conn())


class TestWhatIsRefused:
    @pytest.mark.parametrize("sql", [
        "DELETE FROM t",
        "UPDATE t SET a = 1",
        "INSERT INTO t VALUES (1)",
        "DROP TABLE t",
        "CREATE TABLE t (a int)",
        "BEGIN minha_proc; END;",
    ])
    def test_a_write_is_refused(self, sql):
        with pytest.raises(ReadOnlyViolation):
            check_read_only(sql, _conn())

    def test_a_cte_that_writes_is_refused(self):
        """`WITH x AS (...) INSERT ...` already classifies as INSERT; this
        pins that it stays refused."""
        with pytest.raises(ReadOnlyViolation):
            check_read_only("WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x",
                            _conn())

    def test_an_unclassifiable_statement_is_refused(self):
        """MERGE lands on UNKNOWN. Under a read-only guard, not knowing is a
        refusal -- the whole point is to decline what it cannot see through."""
        with pytest.raises(ReadOnlyViolation):
            check_read_only("MERGE INTO t USING s ON (1=1) "
                            "WHEN MATCHED THEN UPDATE SET a = 1", _conn())

    def test_the_message_names_the_flag(self):
        """A rail that stops you without saying how to proceed deliberately
        is a rail people work around by editing config."""
        with pytest.raises(ReadOnlyViolation, match="--force-write"):
            check_read_only("DELETE FROM t", _conn())

    def test_the_message_names_the_connection(self):
        with pytest.raises(ReadOnlyViolation, match="alvo"):
            check_read_only("DELETE FROM t", _conn())


class TestMultipleStatements:
    """`classify_sql` reads only the FIRST statement while the whole string
    reaches the driver. Measured: classify_sql("SELECT 1; DROP TABLE alvo")
    returns 'SELECT'. On PostgreSQL and SQL Server both would run."""

    def test_two_statements_are_refused_even_when_the_first_is_a_select(self):
        with pytest.raises(ReadOnlyViolation):
            check_read_only("SELECT 1; DROP TABLE alvo", _conn())

    def test_a_trailing_semicolon_is_not_two_statements(self):
        """Refusing this would make the guard unusable: everyone ends a
        statement with a semicolon."""
        check_read_only("SELECT 1 FROM dual;", _conn())

    def test_a_semicolon_inside_a_string_literal_is_not_a_separator(self):
        check_read_only("SELECT 'a;b' FROM dual", _conn())


class TestAWritableConnection:
    """The guard is inert unless the connection says otherwise."""

    @pytest.mark.parametrize("sql", [
        "DELETE FROM t", "DROP TABLE t", "SELECT 1; DROP TABLE t",
    ])
    def test_nothing_is_refused(self, sql):
        check_read_only(sql, _conn(read_only=False))


class TestTheWiring:
    """The guard is only worth anything if it is actually on the paths."""

    def test_execute_adhoc_refuses_before_opening_a_connection(self):
        from unittest.mock import patch

        from dbqm.core.query_engine import execute_adhoc

        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            with pytest.raises(ReadOnlyViolation):
                execute_adhoc("DELETE FROM t", _conn(), {})
        # The point of the guard: refused before the driver was reached.
        mock_get.assert_not_called()

    def test_execute_explain_refuses_a_wrapped_write(self):
        """It wraps caller SQL in EXPLAIN PLAN FOR {sql} with no check that
        the wrapped statement is a query."""
        from unittest.mock import patch

        from dbqm.core.query_engine import execute_explain

        with patch("dbqm.core.query_engine.get_connection") as mock_get:
            with pytest.raises(ReadOnlyViolation):
                execute_explain("DELETE FROM t", _conn(), {})
        mock_get.assert_not_called()

    def test_execute_adhoc_still_runs_a_select_on_a_writable_connection(self):
        """The guard must not become a wall."""
        from unittest.mock import MagicMock, patch

        from dbqm.core.query_engine import execute_adhoc

        db = MagicMock()
        db.cursor.return_value.description = [("a",)]
        db.cursor.return_value.fetchall.return_value = []
        with patch("dbqm.core.query_engine.get_connection", return_value=db):
            r = execute_adhoc("SELECT 1", _conn(read_only=False), {})
        assert r.success is True

class TestExplainThatExecutes:
    """`EXPLAIN` alone is not read-only.

    On PostgreSQL and MySQL, `EXPLAIN ANALYZE DELETE FROM t` **runs the
    delete** -- the plan comes from executing the statement, not from
    predicting it. `classify_sql` reports the whole thing as EXPLAIN, so
    without a second look the guard waves a write through on two of the four
    engines.
    """

    @pytest.mark.parametrize("sql", [
        "EXPLAIN SELECT 1",
        "EXPLAIN PLAN FOR SELECT 1",
        "EXPLAIN ANALYZE SELECT 1",
        "EXPLAIN (FORMAT JSON) SELECT 1",
        "EXPLAIN FORMAT=JSON SELECT 1",
        "EXPLAIN QUERY PLAN SELECT 1",
    ])
    def test_explaining_a_query_passes(self, sql):
        check_read_only(sql, _conn())

    @pytest.mark.parametrize("sql", [
        "EXPLAIN ANALYZE DELETE FROM t",
        "EXPLAIN ANALYZE INSERT INTO t VALUES (1)",
        "EXPLAIN (ANALYZE, FORMAT JSON) UPDATE t SET a = 1",
        "EXPLAIN PLAN FOR DELETE FROM t",
        "EXPLAIN DROP TABLE t",
        "EXPLAIN QUERY PLAN DELETE FROM t",
    ])
    def test_explaining_a_write_is_refused(self, sql):
        with pytest.raises(ReadOnlyViolation):
            check_read_only(sql, _conn())

    def test_an_unrecognised_explain_is_refused(self):
        """Fail closed: a prefix shape this does not know reduces to nothing
        it can vouch for, so it is refused rather than assumed harmless."""
        with pytest.raises(ReadOnlyViolation):
            check_read_only("EXPLAIN", _conn())


class TestTheConnectionIsRead:
    """A defaulted `getattr` would approve anything that is not a Connection,
    including None -- silently, which is the failure this module exists to
    prevent."""

    def test_a_missing_connection_is_an_error_not_a_pass(self):
        with pytest.raises(AttributeError):
            check_read_only("DROP TABLE t", None)


class TestTheTwoTuiOnlyPaths:
    """Routine execution and package compilation exist only in the TUI, so
    the refusal must not point at `--force-write` -- that flag lives on
    `dbqm sql` and there is no CLI subcommand for either. A message naming a
    recourse the user cannot take is worse than a bare refusal: it sends them
    looking for something that is not there."""

    def test_compile_package_refuses_before_any_cursor(self):
        from unittest.mock import MagicMock

        from dbqm.core.package_editor import compile_package

        db = MagicMock()
        with pytest.raises(ReadOnlyViolation):
            compile_package(db, "CREATE OR REPLACE PACKAGE x AS END;", conn=_conn())
        assert db.cursor.call_count == 0

    def test_compile_package_proceeds_on_a_writable_connection(self):
        """The guard must not become a wall."""
        from unittest.mock import MagicMock

        from dbqm.core.package_editor import compile_package

        db = MagicMock()
        compile_package(db, "CREATE OR REPLACE PACKAGE x AS END;",
                        conn=_conn(read_only=False))
        assert db.cursor.call_count == 1

    @pytest.mark.parametrize("mensagem_de", [
        "dbqm.core.object_browser",
        "dbqm.core.package_editor",
    ])
    def test_neither_message_names_an_unreachable_flag(self, mensagem_de):
        import importlib
        import inspect

        fonte = inspect.getsource(importlib.import_module(mensagem_de))
        assert "--force-write" not in fonte, (
            "these paths are TUI-only; --force-write is a flag on `dbqm sql`"
        )
