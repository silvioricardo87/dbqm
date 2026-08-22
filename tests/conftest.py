"""Shared test fixtures."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from dbqm.core.query_engine import QueryResult
from dbqm.core.group_engine import GroupResult, ComparisonResult, ComparisonRow


@pytest.fixture
def tmp_config_dir(tmp_path, monkeypatch):
    """Redirect all config/export paths to a temp directory."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir()
    history_dir = config_dir / "history"
    history_dir.mkdir()

    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()

    # Patch the canonical paths module (source of truth)
    monkeypatch.setattr("dbqm.core.paths.CONFIG_DIR", config_dir)
    monkeypatch.setattr("dbqm.core.paths.EXPORTS_DIR", exports_dir)
    monkeypatch.setattr("dbqm.core.paths.HISTORY_DIR", history_dir)
    monkeypatch.setattr("dbqm.core.paths.TEMPLATES_DIR", templates_dir)
    monkeypatch.setattr("dbqm.core.paths.TEMPLATES_FILE", templates_dir / "templates.json")
    monkeypatch.setattr("dbqm.core.paths.KEY_FILE", config_dir / ".dbqm_key")
    monkeypatch.setattr("dbqm.core.paths.AUDIT_FILE", config_dir / "audit.log")
    monkeypatch.setattr("dbqm.core.paths.CONNECTIONS_FILE", config_dir / "connections.json")
    monkeypatch.setattr("dbqm.core.paths.QUERIES_FILE", config_dir / "queries.json")
    monkeypatch.setattr("dbqm.core.paths.GROUPS_FILE", config_dir / "groups.json")
    monkeypatch.setattr("dbqm.core.paths.SETTINGS_FILE", config_dir / "settings.json")

    # Patch module-level references that imported at load time
    attr_values = {
        "CONFIG_DIR": config_dir,
        "EXPORTS_DIR": exports_dir,
        "HISTORY_DIR": history_dir,
        "TEMPLATES_DIR": templates_dir,
        "TEMPLATES_FILE": templates_dir / "templates.json",
        "KEY_FILE": config_dir / ".dbqm_key",
        "AUDIT_FILE": config_dir / "audit.log",
        "CONNECTIONS_FILE": config_dir / "connections.json",
        "QUERIES_FILE": config_dir / "queries.json",
        "GROUPS_FILE": config_dir / "groups.json",
        "SETTINGS_FILE": config_dir / "settings.json",
    }
    for mod_path in [
        "dbqm.models.connection.CONFIG_DIR",
        "dbqm.models.connection.CONNECTIONS_FILE",
        "dbqm.models.query.CONFIG_DIR",
        "dbqm.models.query.QUERIES_FILE",
        "dbqm.models.group.CONFIG_DIR",
        "dbqm.models.group.GROUPS_FILE",
        "dbqm.models.settings.CONFIG_DIR",
        "dbqm.models.settings.SETTINGS_FILE",
        "dbqm.core.history.HISTORY_DIR",
        "dbqm.core.audit.AUDIT_FILE",
        "dbqm.core.audit.CONFIG_DIR",
        "dbqm.core.exporter.EXPORTS_DIR",
        "dbqm.core.crypto.KEY_FILE",
        "dbqm.core.ddl_extractor.EXPORTS_DIR",
        "dbqm.core.config_portability.EXPORTS_DIR",
        "dbqm.models.template.TEMPLATES_DIR",
        "dbqm.models.template.TEMPLATES_FILE",
    ]:
        attr = mod_path.rsplit(".", 1)[1]
        monkeypatch.setattr(mod_path, attr_values[attr])

    return tmp_path


@pytest.fixture(autouse=True)
def _tema_padrao_para_apps_textual(monkeypatch):
    """Toda App do Textual usada em teste ganha os temas do design system,
    do mesmo jeito que a DBQMApp real ganha em __init__.

    Sem isso, os varios harnesses de teste ad-hoc (`class XxxTestApp(App)`)
    nunca registram plano-escuro/plano-claro, e qualquer DEFAULT_CSS que use
    um token puro (ex.: `$borda`, que ao contrario de `$accent`/`$primary`
    nao e variavel embutida do Textual) quebra a montagem do widget com
    UnresolvedVariableError. Antes desta migracao isso nunca apareceu porque
    so se usavam variaveis embutidas, disponiveis em qualquer tema.
    """
    from textual.app import App as AppTextual

    from dbqm.ui.theme import PADRAO, TEMAS_TEXTUAL

    init_original = AppTextual.__init__

    def init_com_tema(self, *args, **kwargs):
        init_original(self, *args, **kwargs)
        for tema in TEMAS_TEXTUAL.values():
            self.register_theme(tema)
        self.theme = PADRAO

    monkeypatch.setattr(AppTextual, "__init__", init_com_tema)


@pytest.fixture
def sqlite_db():
    """Create an in-memory SQLite database with test tables."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            department TEXT,
            salary REAL
        )
    """)
    cursor.execute("""
        INSERT INTO employees (id, name, department, salary) VALUES
        (1, 'Alice', 'Engineering', 90000),
        (2, 'Bob', 'Sales', 70000),
        (3, 'Carol', 'Engineering', 95000)
    """)
    cursor.execute("""
        CREATE TABLE departments (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        )
    """)
    cursor.execute("INSERT INTO departments VALUES (1, 'Engineering'), (2, 'Sales')")
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def sample_query_result():
    """A simple QueryResult for testing exports."""
    return QueryResult(
        query_name="test_query",
        connection_name="test_conn",
        columns=["id", "name", "value"],
        rows=[[1, "Alice", 100], [2, "Bob", 200]],
        row_count=2,
        elapsed=0.05,
    )


@pytest.fixture
def sample_group_result():
    """A GroupResult for testing group exports."""
    qr1 = QueryResult(
        query_name="q1", connection_name="conn1",
        columns=["id", "status"], rows=[[1, "active"], [2, "inactive"]],
        row_count=2, elapsed=0.1,
    )
    qr2 = QueryResult(
        query_name="q2", connection_name="conn2",
        columns=["id", "status"], rows=[[1, "active"], [2, "active"]],
        row_count=2, elapsed=0.1,
    )
    comparisons = [
        ComparisonResult(
            column="status",
            rows=[
                ComparisonRow(key_value=1, values={"q1": "active", "q2": "active"}, status="OK"),
                ComparisonRow(key_value=2, values={"q1": "inactive", "q2": "active"}, status="DIFF"),
            ],
            total_keys=2, equal_count=1, diff_count=1, absent_count=0, normalized_count=0,
        )
    ]
    return GroupResult(
        group_name="test_group",
        query_results={"q1": qr1, "q2": qr2},
        comparisons=comparisons,
        all_match=False,
        summary_lines=["Coluna: status", "  Iguais: 1", "  Diferentes: 1"],
    )
