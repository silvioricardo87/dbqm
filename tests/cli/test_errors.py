"""Tests for the CLI exit-code table."""
from __future__ import annotations

import pytest

from dbqm.cli.errors import ERROR_CODES, ExitCode, exit_for


class TestExitCode:
    def test_the_two_already_published_keep_their_numbers(self):
        """`connection` shipped 2 and 3 in 1.22.0. Changing them breaks scripts."""
        assert ExitCode.USAGE == 2
        assert ExitCode.CONNECTION_FAILED == 3

    def test_success_is_zero_and_unexpected_is_one(self):
        assert ExitCode.SUCCESS == 0
        assert ExitCode.UNEXPECTED == 1

    def test_sql_error_and_divergent_are_distinct(self):
        assert ExitCode.SQL_ERROR == 4
        assert ExitCode.DIVERGENT == 5
        assert len({int(c) for c in ExitCode}) == len(list(ExitCode))


class TestErrorCodes:
    def test_every_token_maps_to_an_exit_code(self):
        esperados = {
            "usage", "not_found", "validation", "connection_failed",
            "sql_error", "divergent", "unexpected",
        }
        assert set(ERROR_CODES) == esperados
        assert all(isinstance(v, ExitCode) for v in ERROR_CODES.values())

    def test_three_tokens_share_exit_2_on_purpose(self):
        """The string is finer than the number: a script branches on one, a
        reader wants to know which of the three happened."""
        assert exit_for("usage") == ExitCode.USAGE
        assert exit_for("not_found") == ExitCode.USAGE
        assert exit_for("validation") == ExitCode.USAGE

    def test_an_unknown_token_is_a_programming_error(self):
        with pytest.raises(KeyError):
            exit_for("inventado")
