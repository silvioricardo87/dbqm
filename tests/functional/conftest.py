"""The functional harness: a real SQLite file, a registered connection, and
`run_cli` called for real.

Nothing in this directory patches `dbqm.cli.deps`. A test that needs to is
a unit test in the wrong folder, and `test_harness.py` refuses it by
reading the folder's source. The config directory is `tmp_config_dir`'s and
the database is a file under `tmp_path` -- never the developer's home.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

SEED = """
CREATE TABLE clientes (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    status TEXT
);
CREATE TABLE pedidos (
    id INTEGER PRIMARY KEY,
    cliente_id INTEGER REFERENCES clientes(id),
    valor REAL
);
CREATE UNIQUE INDEX ix_clientes_nome ON clientes(nome);
CREATE VIEW v_ativos AS SELECT id, nome FROM clientes WHERE status = 'A';
INSERT INTO clientes VALUES (1, 'Ana', 'A'), (2, 'Bia', 'I'), (3, 'Caio', 'A');
INSERT INTO pedidos VALUES (10, 1, 9.5), (11, 1, 30.0), (12, 3, 20.0), (13, 3, 5.25);
"""


def seed_sqlite(path: Path, script: str = SEED) -> None:
    """Create and seed a SQLite file, closing the handle afterwards -- with
    `filterwarnings = error`, an unclosed connection fails whichever test is
    running at garbage-collection time."""
    db = sqlite3.connect(path)
    try:
        db.executescript(script)
        db.commit()
    finally:
        db.close()


def register_connection(name: str, path: Path, **extra: object) -> None:
    """Register a SQLite connection through the same rules the CLI and the
    TUI use. Not through `run_cli`: the fixture is not the thing under test."""
    from dbqm.core.connection_builder import build, validate
    from dbqm.models.connection import load_connections, save_connections

    values: dict = {"name": name, "db_type": "sqlite", "database": str(path), **extra}
    problems = validate(values)
    assert not problems, problems
    connections = [c for c in load_connections() if c.name != name]
    connections.append(build(values))
    save_connections(connections)


@pytest.fixture
def local_db(tmp_config_dir, tmp_path) -> Path:
    """A seeded SQLite file plus a registered connection named `local`.

    Returns the path. Every functional test runs `run_cli` against this and
    patches nothing. The database is a file, not memory, on purpose: state
    surviving between `run_cli` calls -- a `--commit` that persists, a
    `query add` that a later `run` finds -- is part of what the suite tests.
    """
    path = tmp_path / "local.db"
    seed_sqlite(path)
    register_connection("local", path)
    return path
