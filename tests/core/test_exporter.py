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

    def test_dbms_output(self, tmp_config_dir):
        from dbqm.core.exporter import export_dbms_output
        from dbqm.core.query_engine import AdhocResult
        result = AdhocResult(
            sql_type="PLSQL", connection_name="prod", elapsed=0.12,
            committed=True,
            output_lines=["processando registro 1", "processando registro 2"],
        )
        path = export_dbms_output(
            result, "BEGIN NULL; END;", "2026-06-17 10:00:00", label="meu_bloco",
        )
        assert path.endswith(".txt")
        content = Path(path).read_text(encoding="utf-8")
        # Evidence carries SQL, date/time, output and outcome
        assert "BEGIN NULL; END;" in content
        assert "2026-06-17 10:00:00" in content
        assert "processando registro 1" in content
        assert "processando registro 2" in content
        assert "EVIDENCIA DE EXECUCAO" in content
        assert "Bloco PL/SQL executado" in content

    def test_dbms_output_empty_lines(self, tmp_config_dir):
        from dbqm.core.exporter import export_dbms_output
        from dbqm.core.query_engine import AdhocResult
        result = AdhocResult(sql_type="PLSQL", connection_name="prod")
        path = export_dbms_output(result, "BEGIN NULL; END;", "2026-06-17 10:00:00", label="vazio")
        assert Path(path).exists()
        content = Path(path).read_text(encoding="utf-8")
        assert "(sem saida DBMS_OUTPUT)" in content

    def test_format_dbms_evidence_dml(self):
        from dbqm.core.exporter import format_dbms_evidence
        from dbqm.core.query_engine import AdhocResult
        result = AdhocResult(
            sql_type="UPDATE", connection_name="prod", rows_affected=6,
            committed=True, elapsed=0.04, output_lines=["UPDATE OK"],
        )
        text = format_dbms_evidence(result, "UPDATE t SET x=1", "2026-06-17 11:30:00")
        assert "UPDATE t SET x=1" in text
        assert "2026-06-17 11:30:00" in text
        assert "6 registro(s) afetado(s) - COMMIT" in text
        assert "UPDATE OK" in text

    def test_format_dbms_evidence_error(self):
        from dbqm.core.exporter import format_dbms_evidence
        from dbqm.core.query_engine import AdhocResult
        result = AdhocResult(
            sql_type="PLSQL", connection_name="prod", success=False,
            error="ORA-00001: unique constraint",
        )
        text = format_dbms_evidence(result, "BEGIN NULL; END;", "2026-06-17 12:00:00")
        assert "ERRO: ORA-00001" in text


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


class TestExportDirResolution:
    """Path resolution honors settings (and the EXPORTS_DIR override for tests)."""

    def test_query_exports_go_directly_in_base_dir(self, tmp_config_dir, sample_query_result):
        """Queries never get a category subfolder, even when EXPORTS_DIR override is active."""
        path = Path(export_query_csv(sample_query_result, "employees"))
        # parent should be EXPORTS_DIR itself, not EXPORTS_DIR/consultas/employees
        assert path.parent == tmp_config_dir / "exports"

    def test_query_export_resolves_default_export_dir_from_settings(
        self, tmp_config_dir, sample_query_result, monkeypatch
    ):
        """Without the EXPORTS_DIR test override, exports use Settings.default_export_dir."""
        from dbqm.core import exporter as exporter_module
        from dbqm.models.settings import Settings, save_settings

        target = tmp_config_dir / "custom-exports"
        target.mkdir()
        save_settings(Settings(default_export_dir=str(target), export_dir_prompted=True))
        monkeypatch.setattr(exporter_module, "EXPORTS_DIR", None)

        path = Path(export_query_csv(sample_query_result, "employees"))
        assert path.parent == target

    def test_query_export_falls_back_to_cwd_when_unset(
        self, tmp_path, sample_query_result, monkeypatch
    ):
        """Without any setting and without EXPORTS_DIR override, queries land in CWD."""
        from dbqm.core import exporter as exporter_module
        from dbqm.models.settings import Settings, save_settings

        cwd_dir = tmp_path / "cwd"
        cwd_dir.mkdir()
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        settings_file = config_dir / "settings.json"

        monkeypatch.setattr(exporter_module, "EXPORTS_DIR", None)
        monkeypatch.setattr("dbqm.core.paths.CONFIG_DIR", config_dir)
        monkeypatch.setattr("dbqm.core.paths.SETTINGS_FILE", settings_file)
        monkeypatch.setattr("dbqm.models.settings.CONFIG_DIR", config_dir)
        monkeypatch.setattr("dbqm.models.settings.SETTINGS_FILE", settings_file)
        save_settings(Settings())  # explicit empty default_export_dir
        monkeypatch.chdir(cwd_dir)

        path = Path(export_query_csv(sample_query_result, "employees"))
        assert path.parent == cwd_dir

    def test_group_export_creates_subfolder_when_subdirs_enabled(
        self, tmp_config_dir, sample_group_result
    ):
        """Groups respect create_export_subdirs setting; with EXPORTS_DIR override it is forced True."""
        path = Path(export_group_csv(sample_group_result))
        # Should be nested under grupos/{normalized_label}/
        assert "grupos" in path.parts
        assert path.parent.parent == tmp_config_dir / "exports" / "grupos"

    def test_group_export_flat_when_subdirs_disabled(
        self, tmp_path, sample_group_result, monkeypatch
    ):
        """When create_export_subdirs is OFF (and no test override is active), groups go flat."""
        from dbqm.core import exporter as exporter_module
        from dbqm.models.settings import Settings, save_settings

        target = tmp_path / "flat"
        target.mkdir()
        config_dir = tmp_path / "cfg"
        config_dir.mkdir()
        settings_file = config_dir / "settings.json"

        monkeypatch.setattr(exporter_module, "EXPORTS_DIR", None)
        monkeypatch.setattr("dbqm.core.paths.CONFIG_DIR", config_dir)
        monkeypatch.setattr("dbqm.core.paths.SETTINGS_FILE", settings_file)
        monkeypatch.setattr("dbqm.models.settings.CONFIG_DIR", config_dir)
        monkeypatch.setattr("dbqm.models.settings.SETTINGS_FILE", settings_file)
        save_settings(Settings(
            default_export_dir=str(target),
            export_dir_prompted=True,
            create_export_subdirs=False,
        ))

        path = Path(export_group_csv(sample_group_result))
        # No "grupos" or label subfolder — flat in target.
        assert path.parent == target


class TestFilenameTruncation:
    """Long filenames must be truncated to stay under MAX_PATH on Windows."""

    def test_long_params_do_not_overflow_max_path(self, tmp_config_dir, sample_query_result):
        """Massive parameter values produce a path well under the conservative cap."""
        from dbqm.core.exporter import _MAX_PATH_LEN

        huge = {"key" + str(i): "x" * 200 for i in range(20)}
        path = Path(export_query_csv(sample_query_result, "employees", params=huge))
        assert len(str(path)) <= _MAX_PATH_LEN
        # Extension must survive truncation.
        assert path.suffix == ".csv"
        assert path.exists()

    def test_extension_preserved_after_truncation(self, tmp_path):
        """`_fit_path` keeps the file extension intact when shortening the body."""
        from dbqm.core.exporter import _fit_path, _MAX_PATH_LEN

        long_name = "x" * (_MAX_PATH_LEN + 50) + ".json"
        out = _fit_path(tmp_path, long_name)
        assert out.suffix == ".json"
        assert len(str(out)) <= _MAX_PATH_LEN
