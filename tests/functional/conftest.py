"""The functional harness: a real SQLite file, a registered connection, and
`run_cli` called for real.

Nothing in this directory patches `dbqm.cli.deps`. A test that needs to is
a unit test in the wrong folder, and `test_harness.py` refuses it by
reading the folder's source. The config directory is `tmp_config_dir`'s and
the database is a file under `tmp_path` -- never the developer's home.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from dbqm.cli import run_cli

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


def invoke(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Run the CLI for real and return `(exit_code, stdout, stderr)`.

    `run_cli` returns on success and raises `SystemExit` on failure; the
    tests care about the number either way, so this folds both into one.
    """
    try:
        run_cli(argv)
        code = 0
    except SystemExit as e:
        code = int(e.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def envelope(argv: list[str], capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, Any]]:
    """`invoke` under the contract: the one JSON object the command emitted.

    On success it is on stdout; on failure, on stderr. A divergence (exit 5)
    is the one case with both a non-zero exit and an `ok` object on stdout,
    so the stream is chosen by what stdout holds, not by the exit code.
    stderr may carry progress lines next to a success (`ddl` reports each
    object there so stdout stays parseable), which is why it is not
    required to be empty here -- `test_output_contract.py` asserts the
    streams where the contract says something about them.
    """
    code, out, err = invoke(argv, capsys)
    return code, json.loads(out if out.strip() else err)


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


#: What `local2` holds that `local` does not: pedido 13 is worth 6.0, not
#: 5.25. One row, one column, so a divergence is real and its counts are
#: known (4 keys, 3 equal, 1 different).
LOCAL2_SEED = SEED.replace("(13, 3, 5.25)", "(13, 3, 6.0)")


@pytest.fixture
def local2_db(local_db, tmp_path) -> Path:
    """A second seeded file and a connection named `local2`, identical to
    `local` except for `LOCAL2_SEED`'s one row. What the comparison
    commands compare against."""
    path = tmp_path / "local2.db"
    seed_sqlite(path, LOCAL2_SEED)
    register_connection("local2", path)
    return path


@pytest.fixture
def read_only_db(local_db) -> Path:
    """`local_db` plus a second connection, `ro`, on the same file with
    `read_only=True`. Same data, so a refusal can be checked by reading the
    row back through `local` and finding it untouched."""
    register_connection("ro", local_db, read_only=True)
    return local_db


@pytest.fixture
def broken_db(tmp_config_dir, tmp_path) -> Path:
    """A connection named `broken` whose `database` is a directory.

    `sqlite3.connect` creates a missing file, so a path that does not exist
    would connect fine; a directory is what makes the driver refuse
    (`unable to open database file`), which is the only way to produce a real
    `connection_failed` on this engine."""
    path = tmp_path / "not-a-file"
    path.mkdir()
    register_connection("broken", path)
    return path
