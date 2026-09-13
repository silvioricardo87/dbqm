"""The CLI remaps two of `core/`'s error messages from `sql_error` to `usage`,
because in both cases the statement was never sent to the database. The remap
matches the message verbatim, so it goes silently dead if `core/` rewords one.
This guard fails instead."""

from pathlib import Path

import dbqm.core.query_engine as query_engine
from dbqm.cli.commands.query import _USAGE_SQL_MESSAGES, _sql_error_code


def test_every_remapped_message_still_exists_in_core():
    fonte = Path(query_engine.__file__).read_text(encoding="utf-8")
    for mensagem in _USAGE_SQL_MESSAGES:
        assert mensagem in fonte, (
            f"query_engine.py no longer contains {mensagem!r}; the CLI still "
            "remaps it to `usage`, so the remap is now dead code"
        )


def test_a_remapped_message_is_usage():
    for mensagem in _USAGE_SQL_MESSAGES:
        assert _sql_error_code(mensagem) == "usage"


def test_anything_else_is_sql_error():
    assert _sql_error_code("ORA-00942: table or view does not exist") == "sql_error"
    assert _sql_error_code(None) == "sql_error"


def test_the_unsupported_explain_prefix_still_exists_in_core():
    """`--explain` on an engine that has none is a usage error, matched by
    prefix because the message names the engine. A reword in `query_engine`
    would make that remap dead code with nothing failing."""
    from dbqm.cli.commands.query import _UNSUPPORTED_EXPLAIN_PREFIX

    fonte = Path(query_engine.__file__).read_text(encoding="utf-8")
    assert _UNSUPPORTED_EXPLAIN_PREFIX in fonte


def test_the_ddl_not_found_suffix_still_exists_in_its_extractor():
    """`ddl` answers `not_found` by matching what `ddl_extractor` writes when
    the object is absent. Same fragility, same guard."""
    import dbqm.core.ddl_extractor as ddl_extractor
    from dbqm.cli.commands.inspect import _DDL_NOT_FOUND

    fonte = Path(ddl_extractor.__file__).read_text(encoding="utf-8")
    assert _DDL_NOT_FOUND in fonte


def test_the_explain_prefix_is_usage_and_a_driver_error_is_not():
    from dbqm.cli.commands.query import _UNSUPPORTED_EXPLAIN_PREFIX

    assert _sql_error_code(_UNSUPPORTED_EXPLAIN_PREFIX + "mysql.", "") == "usage"
    assert _sql_error_code("ORA-00942: tabela inexistente", "") == "sql_error"
