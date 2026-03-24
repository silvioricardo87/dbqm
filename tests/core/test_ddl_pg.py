"""Tests for PostgreSQL DDL extraction."""
from unittest.mock import MagicMock, call

from dbqm.core.ddl_extractor import ExtractionResult
from dbqm.core.ddl_pg import extract_pg_ddl, _pg_format_type


class TestPgFormatType:
    def test_varchar(self):
        assert _pg_format_type("character varying", 255, None, None) == "varchar(255)"

    def test_char(self):
        assert _pg_format_type("character", 10, None, None) == "char(10)"

    def test_numeric_with_scale(self):
        assert _pg_format_type("numeric", None, 10, 2) == "numeric(10,2)"

    def test_numeric_without_scale(self):
        assert _pg_format_type("numeric", None, 10, None) == "numeric(10)"

    def test_plain_type(self):
        assert _pg_format_type("integer", None, None, None) == "integer"
        assert _pg_format_type("text", None, None, None) == "text"


class TestExtractPgDdl:
    def test_table_detected(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor

        # First query: information_schema.tables → BASE TABLE
        # Then columns, constraints, indexes
        call_count = [0]

        def execute_side(sql, params=None):
            idx = call_count[0]
            call_count[0] += 1
            if idx == 0:
                cursor.fetchone.return_value = ("BASE TABLE",)
                cursor.fetchall.return_value = []
            elif idx == 1:
                cursor.fetchall.return_value = [
                    ("id", "integer", None, None, None, "NO", None),
                    ("name", "character varying", 100, None, None, "YES", None),
                ]
            elif idx == 2:
                cursor.fetchall.return_value = []
            elif idx == 3:
                cursor.fetchall.return_value = []

        cursor.execute.side_effect = execute_side

        result = ExtractionResult(
            object_name="users", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_pg_ddl(db, "users", result)
        assert result.object_type == "TABLE"
        assert len(result.objects) >= 1
        assert "CREATE TABLE" in result.objects[0].ddl

    def test_not_found(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor

        call_count = [0]

        def execute_side(sql, params=None):
            idx = call_count[0]
            call_count[0] += 1
            cursor.fetchone.return_value = None

        cursor.execute.side_effect = execute_side

        result = ExtractionResult(
            object_name="missing", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_pg_ddl(db, "missing", result)
        assert len(result.errors) == 1
        assert "nao encontrado" in result.errors[0]
