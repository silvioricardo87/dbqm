"""Tests for export functions."""
import csv
import json
from pathlib import Path

import pytest

from dbqm.core.exporter import (
    export_query_csv, export_query_json, export_query_txt, export_sql_file,
    export_individual_txt, export_group_csv, export_group_json, export_group_txt,
    export_group_flat_csv, export_group_flat_json, export_group_flat_txt,
    _sanitize, _params_suffix, _worst_status, _status_label, _flat_status_label,
    _build_query_txt_lines,
)


class TestHelpers:
    def test_sanitize(self):
        assert _sanitize("hello world/foo") == "hello_world_foo"
        assert _sanitize("a\\b") == "a_b"

    def test_params_suffix_empty(self):
        assert _params_suffix(None) == ""
        assert _params_suffix({}) == ""

    def test_params_suffix(self):
        result = _params_suffix({"id": "123"})
        assert "id-123" in result
        assert result.startswith("_")

    def test_worst_status(self):
        assert _worst_status(["OK", "OK"]) == "OK"
        assert _worst_status(["OK", "DIFF"]) == "DIFF"
        assert _worst_status(["DIFF", "ABSENT"]) == "ABSENT"
        assert _worst_status(["OK", "OK*"]) == "OK*"

    def test_status_label(self):
        assert _status_label("OK") == "v OK"
        assert _status_label("DIFF") == "! DIFF"

    def test_flat_status_label(self):
        assert _flat_status_label("OK") == "Igual"
        assert _flat_status_label("DIFF") == "Diferente"
        assert _flat_status_label("ABSENT") == "Ausente"

    def test_build_query_txt_lines(self, sample_query_result):
        lines = _build_query_txt_lines(sample_query_result)
        assert any("test_query" in l for l in lines)
        assert any("Alice" in l for l in lines)

    def test_build_query_txt_lines_empty(self):
        from dbqm.core.query_engine import QueryResult
        qr = QueryResult(query_name="q", connection_name="c", columns=[], rows=[], row_count=0, elapsed=0)
        lines = _build_query_txt_lines(qr)
        assert len(lines) > 0  # at least header lines


class TestQueryExports:
    def test_csv(self, tmp_config_dir, sample_query_result):
        path = export_query_csv(sample_query_result, "employees")
        assert Path(path).exists()
        with open(path) as f:
            reader = csv.reader(f)
            rows = list(reader)
        assert rows[0] == ["id", "name", "value"]
        assert len(rows) == 3  # header + 2 data rows

    def test_json(self, tmp_config_dir, sample_query_result):
        path = export_query_json(sample_query_result, "employees")
        data = json.loads(Path(path).read_text())
        assert data["query"] == "test_query"
        assert len(data["rows"]) == 2
        assert data["rows"][0]["name"] == "Alice"

    def test_txt(self, tmp_config_dir, sample_query_result):
        path = export_query_txt(sample_query_result, "employees")
        content = Path(path).read_text()
        assert "test_query" in content
        assert "Alice" in content

    def test_sql_file(self, tmp_config_dir):
        path = export_sql_file("SELECT 1 FROM dual", "test")
        content = Path(path).read_text()
        assert "SELECT 1 FROM dual" in content

    def test_individual_txt(self, tmp_config_dir, sample_query_result):
        path = export_individual_txt(sample_query_result, sql="SELECT * FROM t", params={"id": "1"})
        content = Path(path).read_text()
        assert "SELECT * FROM t" in content
        assert "id" in content


class TestGroupExports:
    def test_group_csv(self, tmp_config_dir, sample_group_result):
        path = export_group_csv(sample_group_result)
        assert Path(path).exists()
        content = Path(path).read_text()
        assert "test_group" in content

    def test_group_json(self, tmp_config_dir, sample_group_result):
        path = export_group_json(sample_group_result)
        data = json.loads(Path(path).read_text())
        assert data["group"] == "test_group"
        assert data["all_match"] is False
        assert len(data["keys"]) == 2

    def test_group_txt(self, tmp_config_dir, sample_group_result):
        path = export_group_txt(sample_group_result)
        content = Path(path).read_text()
        assert "DIVERGENTE" in content

    def test_group_flat_csv(self, tmp_config_dir, sample_group_result):
        path = export_group_flat_csv(sample_group_result)
        assert Path(path).exists()

    def test_group_flat_json(self, tmp_config_dir, sample_group_result):
        path = export_group_flat_json(sample_group_result)
        data = json.loads(Path(path).read_text())
        assert data["group"] == "test_group"
        assert len(data["columns"]) == 1

    def test_group_flat_txt(self, tmp_config_dir, sample_group_result):
        path = export_group_flat_txt(sample_group_result)
        content = Path(path).read_text()
        assert "status" in content
