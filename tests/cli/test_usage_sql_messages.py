"""How the CLI tells one kind of failure from another.

It used to read the message: `core/` wrote a sentence, and
`commands/query.py` kept a copy of that sentence to recognise it by. The
whole file was a guard against `core/` rewording one and the remap going
silently dead.

A catalogue ends that arrangement, and not only because the wording moved.
The message is a translation now, so matching it would have classified
correctly for one language and silently wrongly for every other -- a
`sql_error` where the caller should have read `usage`, in the language the
caller chose. What travels instead is `error_kind`, which no translation
touches. These tests guard that.
"""
from __future__ import annotations

import pytest

from dbqm.cli.commands.inspect import _ddl_error_code
from dbqm.cli.commands.query import _sql_error_code
from dbqm.core.ddl_extractor import ExtractionResult
from dbqm.i18n import set_language, t


@pytest.fixture(autouse=True)
def _restore_the_language():
    previous = set_language(None)
    yield
    set_language(previous)


class TestSqlFailures:
    def test_bad_input_core_never_sent_is_usage(self):
        assert _sql_error_code("whatever", "usage") == "usage"

    def test_a_statement_the_driver_rejected_is_sql_error(self):
        assert _sql_error_code("ORA-00942: table or view does not exist", "") == "sql_error"
        assert _sql_error_code(None, "") == "sql_error"

    def test_the_database_never_answering_outranks_everything(self):
        assert _sql_error_code("anything", "connection") == "connection_failed"

    def test_the_guard_refusing_is_its_own_token(self):
        assert _sql_error_code("anything", "read_only") == "read_only"

    @pytest.mark.parametrize("language", ["en", "pt"])
    def test_the_classification_does_not_depend_on_the_language(self, language):
        """The point of the change: the same condition, read by a caller in
        either language, is the same token."""
        set_language(language)
        assert _sql_error_code(t("sql.select_only"), "usage") == "usage"
        assert _sql_error_code(t("sql.unsupported_type"), "usage") == "usage"
        assert _sql_error_code(t("sql.explain_unsupported", type="mysql"), "usage") == "usage"


class TestDdlFailures:
    @staticmethod
    def _result(**kwargs) -> ExtractionResult:
        base = {"object_name": "T", "object_type": "TABLE", "owner": "", "connection_name": "c"}
        return ExtractionResult(**{**base, **kwargs})

    def test_an_object_that_is_not_there_is_not_found(self):
        assert _ddl_error_code(self._result(not_found=True)) == "not_found"

    def test_an_extraction_that_failed_is_sql_error(self):
        assert _ddl_error_code(self._result(errors=["ORA-01031"])) == "sql_error"

    @pytest.mark.parametrize("language", ["en", "pt"])
    def test_it_does_not_depend_on_the_language_either(self, language):
        set_language(language)
        result = self._result(errors=[t("ddl.object_not_found", name="T")],
                                    not_found=True)
        assert _ddl_error_code(result) == "not_found"


def test_core_no_longer_needs_the_cli_to_recognise_its_sentences():
    """The two constants this file was built around are gone. If either comes
    back, the coupling it represents came back with it."""
    import dbqm.cli.commands.query as query

    assert not hasattr(query, "_USAGE_SQL_MESSAGES")
    assert not hasattr(query, "_UNSUPPORTED_EXPLAIN_PREFIX")
