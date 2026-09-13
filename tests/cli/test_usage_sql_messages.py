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
