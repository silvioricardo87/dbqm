"""Tests for MySQL DDL extraction."""
from unittest.mock import MagicMock

from dbqm.core.ddl_extractor import ExtractionResult
from dbqm.core.ddl_mysql import extract_mysql_ddl


class TestExtractMysqlDdl:
    def _mock_db(self, show_results):
        """Create a mock DB where SHOW CREATE returns results in order."""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value = cursor

        call_idx = [0]

        def execute_side(sql, *args, **kwargs):
            idx = call_idx[0]
            call_idx[0] += 1
            if idx < len(show_results):
                entry = show_results[idx]
                if entry is None:
                    raise Exception("not found")
                cursor.fetchone.return_value = entry
            else:
                raise Exception("not found")

        cursor.execute.side_effect = execute_side
        return db

    def test_extract_table(self):
        db = self._mock_db([("my_table", "CREATE TABLE my_table (id INT);")])
        result = ExtractionResult(
            object_name="my_table", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "my_table", result)
        assert result.object_type == "TABLE"
        assert len(result.objects) == 1
        assert "CREATE TABLE" in result.objects[0].ddl

    def test_extract_view(self):
        db = self._mock_db([None, ("my_view", "CREATE VIEW my_view AS SELECT 1;")])
        result = ExtractionResult(
            object_name="my_view", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "my_view", result)
        assert result.object_type == "VIEW"

    def test_extract_procedure(self):
        db = self._mock_db([None, None, ("my_proc", "sql_mode", "CREATE PROCEDURE my_proc() BEGIN END;")])
        result = ExtractionResult(
            object_name="my_proc", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "my_proc", result)
        assert result.object_type == "PROCEDURE"

    def test_extract_function(self):
        db = self._mock_db([None, None, None, ("my_func", "sql_mode", "CREATE FUNCTION my_func() RETURNS INT BEGIN RETURN 1; END;")])
        result = ExtractionResult(
            object_name="my_func", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "my_func", result)
        assert result.object_type == "FUNCTION"

    def test_not_found(self):
        db = self._mock_db([None, None, None, None])
        result = ExtractionResult(
            object_name="missing", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "missing", result)
        assert len(result.objects) == 0
        assert len(result.errors) == 1

    def test_progress_callback(self):
        progress_calls = []
        db = self._mock_db([("tbl", "CREATE TABLE tbl (id INT);")])
        result = ExtractionResult(
            object_name="tbl", object_type="UNKNOWN",
            owner="", connection_name="test",
        )
        extract_mysql_ddl(db, "tbl", result, on_progress=lambda *a: progress_calls.append(a))
        assert len(progress_calls) == 1
