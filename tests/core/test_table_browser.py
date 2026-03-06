"""Tests for table browser — identifier validation and SQLite integration."""
import sqlite3
import pytest
from dbqm.core.table_browser import _validate_identifier


class TestValidateIdentifier:
    def test_valid_simple(self):
        assert _validate_identifier("employees") == "employees"

    def test_valid_with_underscore(self):
        assert _validate_identifier("my_table") == "my_table"

    def test_valid_with_dot(self):
        assert _validate_identifier("schema.table") == "schema.table"

    def test_valid_with_hash(self):
        assert _validate_identifier("#temp") == "#temp"

    def test_invalid_space(self):
        with pytest.raises(ValueError):
            _validate_identifier("my table")

    def test_invalid_semicolon(self):
        with pytest.raises(ValueError):
            _validate_identifier("table; DROP TABLE x")

    def test_invalid_dash(self):
        with pytest.raises(ValueError):
            _validate_identifier("my-table")

    def test_empty(self):
        with pytest.raises(ValueError):
            _validate_identifier("")
