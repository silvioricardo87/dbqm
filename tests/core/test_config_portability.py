"""Tests for config export/import portability."""
import json
from pathlib import Path

import pytest

from dbqm.core.config_portability import export_configs, import_configs
from dbqm.models.connection import Connection, save_connections
from dbqm.models.query import Query, save_queries, load_queries
from dbqm.models.group import Group, save_groups
from dbqm.models.template import Template, save_templates, load_templates
from dbqm.core.crypto import encrypt


class TestConfigPortability:
    def test_export_creates_file(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        # Need some data to export
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])
        save_groups([Group(name="g1", description="d", queries=["q1"], join_key="id")])

        path = export_configs("bundlepass")
        assert Path(path).exists()
        data = json.loads(Path(path).read_text())
        assert data["version"] == 1
        assert len(data["connections"]) == 1
        assert len(data["queries"]) == 1
        assert len(data["groups"]) == 1

    def test_round_trip(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])

        path = export_configs("pass123")

        # Clear existing data
        save_connections([])
        save_queries([])
        save_groups([])

        summary = import_configs(path, "pass123")
        assert summary["connections"] == 1
        assert summary["queries"] == 1

    def test_import_skips_duplicates(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])

        path = export_configs("pass")

        # Import again without clearing - should skip
        summary = import_configs(path, "pass")
        assert summary["skipped"] == 2
        assert summary["connections"] == 0
        assert summary["queries"] == 0

    def test_selective_export(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_queries([Query(name="q1", connection="c1", sql="SELECT 1")])

        path = export_configs("pass", include_connections=False)
        data = json.loads(Path(path).read_text())
        assert "connections" not in data
        assert "queries" in data


class TestConfigPortabilityTemplates:
    def test_export_includes_templates(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_templates([
            Template(name="tpl1", description="desc", content="{{campo1}} {{campo2}}"),
        ])

        path = export_configs("pass")
        data = json.loads(Path(path).read_text())
        assert "templates" in data
        assert len(data["templates"]) == 1
        assert data["templates"][0]["name"] == "tpl1"
        assert data["templates"][0]["content"] == "{{campo1}} {{campo2}}"

    def test_import_templates(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_templates([
            Template(name="tpl_a", description="A", content="Hello {{name}}"),
            Template(name="tpl_b", description="B", content="{{x}} + {{y}}"),
        ])

        path = export_configs("pass")

        # Clear and reimport
        save_templates([])
        save_connections([])

        summary = import_configs(path, "pass")
        assert summary["templates"] == 2

        loaded = load_templates()
        assert len(loaded) == 2
        names = {t.name for t in loaded}
        assert names == {"tpl_a", "tpl_b"}

    def test_import_templates_skips_duplicates(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_templates([Template(name="tpl1", description="", content="{{x}}")])

        path = export_configs("pass")

        # Import without clearing — template should be skipped
        summary = import_configs(path, "pass")
        assert summary["templates"] == 0
        assert summary["skipped"] >= 1

    def test_selective_export_excludes_templates(self, tmp_config_dir, monkeypatch):
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_templates([Template(name="tpl1", description="", content="{{x}}")])

        path = export_configs("pass", include_templates=False)
        data = json.loads(Path(path).read_text())
        assert "templates" not in data

    def test_round_trip_templates_with_groups(self, tmp_config_dir, monkeypatch):
        """Templates and groups with template references survive export/import."""
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])
        save_templates([
            Template(name="inv_tpl", description="investigacao", content="ETAPA: {{etapa1}}"),
        ])
        save_groups([
            Group(
                name="g1", description="d", queries=["q1", "q2"], join_key="id",
                template="inv_tpl",
                template_fields={"etapa1": "query:q1:_count"},
            ),
        ])

        path = export_configs("pass")

        save_connections([])
        save_templates([])
        save_groups([])

        summary = import_configs(path, "pass")
        assert summary["templates"] == 1
        assert summary["groups"] == 1

        from dbqm.models.group import load_groups
        groups = load_groups()
        assert groups[0].template == "inv_tpl"
        assert groups[0].template_fields == {"etapa1": "query:q1:_count"}

    def test_import_bundle_without_templates_key(self, tmp_config_dir, monkeypatch):
        """Bundles from older versions (no templates key) import without error."""
        monkeypatch.setattr("dbqm.core.config_portability.EXPORTS_DIR", tmp_config_dir / "exports")
        save_connections([Connection(name="c1", db_type="oracle", user="u", password=encrypt("pw"))])

        path = export_configs("pass", include_templates=False)

        # Simulate old bundle format (no templates key at all)
        data = json.loads(Path(path).read_text())
        assert "templates" not in data

        summary = import_configs(path, "pass")
        assert summary["templates"] == 0
