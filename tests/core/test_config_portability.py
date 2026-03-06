"""Tests for config export/import portability."""
import json
from pathlib import Path

import pytest

from dbqm.core.config_portability import export_configs, import_configs
from dbqm.models.connection import Connection, save_connections
from dbqm.models.query import Query, save_queries, load_queries
from dbqm.models.group import Group, save_groups
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
