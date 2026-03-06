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

    # Patch constants
    monkeypatch.setattr("dbqm.core.constants.CONFIG_DIR", config_dir)
    monkeypatch.setattr("dbqm.core.constants.EXPORTS_DIR", exports_dir)

    # Patch module-level references that import CONFIG_DIR at load time
    for mod_path in [
        "dbqm.models.connection.CONFIG_DIR",
        "dbqm.models.connection.CONNECTIONS_FILE",
        "dbqm.models.query.CONFIG_DIR",
        "dbqm.models.query.QUERIES_FILE",
        "dbqm.models.group.CONFIG_DIR",
        "dbqm.models.group.GROUPS_FILE",
        "dbqm.models.settings.SETTINGS_FILE",
        "dbqm.core.history.HISTORY_DIR",
        "dbqm.core.audit.AUDIT_FILE",
        "dbqm.core.exporter.EXPORTS_DIR",
    ]:
        parts = mod_path.rsplit(".", 1)
        mod, attr = parts[0], parts[1]
        if attr == "CONFIG_DIR":
            monkeypatch.setattr(mod_path, config_dir)
        elif attr == "CONNECTIONS_FILE":
            monkeypatch.setattr(mod_path, config_dir / "connections.json")
        elif attr == "QUERIES_FILE":
            monkeypatch.setattr(mod_path, config_dir / "queries.json")
        elif attr == "GROUPS_FILE":
            monkeypatch.setattr(mod_path, config_dir / "groups.json")
        elif attr == "SETTINGS_FILE":
            monkeypatch.setattr(mod_path, config_dir / "settings.json")
        elif attr == "HISTORY_DIR":
            monkeypatch.setattr(mod_path, history_dir)
        elif attr == "AUDIT_FILE":
            monkeypatch.setattr(mod_path, config_dir / "audit.log")
        elif attr == "EXPORTS_DIR":
            monkeypatch.setattr(mod_path, exports_dir)

    return tmp_path


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
