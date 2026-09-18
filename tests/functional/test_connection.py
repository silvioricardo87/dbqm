"""docs/qa/connections.md — the CRUD verbs of connection, query and group.

Under pytest stdin is not a terminal, which is exactly the condition the
`rm`-without-`--yes` rows describe; nothing is patched to get there.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.functional.conftest import envelope, seed_sqlite


def _add_local(path: Path, capsys, name: str = "local", **extra: str) -> tuple[int, dict]:
    argv = ["connection", "add", name, "--type", "sqlite", "--database", str(path), "--no-password"]
    for chave, valor in extra.items():
        argv += [f"--{chave}", valor]
    return envelope([*argv, "-f", "json"], capsys)


@pytest.fixture
def arquivo(tmp_config_dir, tmp_path) -> Path:
    """A seeded file and no connection: the tests register it themselves,
    through the CLI, because `add` is what they test."""
    path = tmp_path / "local.db"
    seed_sqlite(path)
    return path


@pytest.fixture
def local(arquivo, capsys) -> Path:
    code, body = _add_local(arquivo, capsys, description="seed")
    assert code == 0 and body["data"] == {"name": "local", "created": True}
    return arquivo


# QA-CONN-001
def test_add_creates_a_connection_that_answers(arquivo, capsys):
    code, body = _add_local(arquivo, capsys, description="seed")
    assert code == 0
    assert body["command"] == "connection.add"
    assert body["data"] == {"name": "local", "created": True}
    code, body = envelope(["test", "local", "-f", "json"], capsys)
    assert code == 0 and body["ok"] is True


# QA-CONN-002
def test_add_refuses_a_duplicate(local, capsys):
    code, body = _add_local(local, capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Conexao "local" ja existe.'


# QA-CONN-003
def test_sqlite_needs_a_database(tmp_config_dir, capsys):
    code, body = envelope(["connection", "add", "semdb", "--type", "sqlite", "--no-password", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Give the SQLite database file (or :memory:)."


# QA-CONN-004
def test_sqlite_refuses_a_host(arquivo, capsys):
    code, body = _add_local(arquivo, capsys, name="comhost", host="x")
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "SQLite does not use host; leave it blank."


# QA-CONN-005
def test_update_changes_only_what_it_is_given(local, capsys):
    _, antes = envelope(["connection", "show", "local", "-f", "json"], capsys)
    code, body = envelope(["connection", "update", "local", "--read-only", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "local", "updated": True}
    _, depois = envelope(["connection", "show", "local", "-f", "json"], capsys)
    assert antes["data"]["read_only"] is False
    assert depois["data"]["read_only"] is True
    for campo in ("description", "db_type", "database", "created_at"):
        assert depois["data"][campo] == antes["data"][campo]


# QA-CONN-006
def test_update_of_an_unknown_name_is_not_found(tmp_config_dir, capsys):
    code, body = envelope(["connection", "update", "nope", "--read-only", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Conexao "nope" nao encontrada.'


# QA-CONN-007
def test_show_returns_the_record(local, capsys):
    code, body = envelope(["connection", "show", "local", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "connection.show"
    assert body["data"]["name"] == "local"
    assert body["data"]["db_type"] == "sqlite"
    assert body["data"]["database"] == str(local)
    assert body["data"]["description"] == "seed"
    assert body["data"]["read_only"] is False


# QA-CONN-008
def test_list_shows_the_file_as_the_target(local, capsys):
    code, body = envelope(["connection", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == [{"name": "local", "db_type": "sqlite", "target": str(local), "read_only": False}]


# QA-CONN-009
def test_rm_without_yes_off_a_tty_is_refused_and_keeps_it(local, capsys):
    code, body = envelope(["connection", "rm", "local", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Use --yes para remover sem confirmacao."
    code, _ = envelope(["connection", "show", "local", "-f", "json"], capsys)
    assert code == 0


# QA-CONN-010
def test_rm_with_yes_removes_it(local, capsys):
    code, body = envelope(["connection", "rm", "local", "--yes", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "local", "removed": True}
    code, body = envelope(["connection", "show", "local", "-f", "json"], capsys)
    assert code == 2 and body["error"]["code"] == "not_found"


# --- query ---------------------------------------------------------------

@pytest.fixture
def q1(local, capsys) -> str:
    code, body = envelope(
        ["query", "add", "q1", "--connection", "local", "--sql", "SELECT 1",
         "--description", "d", "--folder", "f", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "q1", "created": True}
    return "q1"


# QA-CONN-011
def test_query_add_then_show(q1, capsys):
    code, body = envelope(["query", "show", q1, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "query.show"
    assert body["data"]["connection"] == "local"
    assert body["data"]["sql"] == "SELECT 1"
    assert body["data"]["description"] == "d"
    assert body["data"]["folder"] == "f"
    assert body["data"]["is_favorite"] is False


# QA-CONN-012
def test_query_add_refuses_a_duplicate(q1, capsys):
    code, body = envelope(["query", "add", q1, "--connection", "local", "--sql", "SELECT 2", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Consulta "q1" ja existe.'
    _, body = envelope(["query", "show", q1, "-f", "json"], capsys)
    assert body["data"]["sql"] == "SELECT 1"


# QA-CONN-013
def test_query_add_needs_a_registered_connection(local, capsys):
    code, body = envelope(["query", "add", "q2", "--sql", "SELECT 1", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Selecione uma conexao."
    code, body = envelope(["query", "add", "q3", "--connection", "nope", "--sql", "SELECT 1", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Conexao "nope" nao encontrada.'


# QA-CONN-014
def test_query_update_changes_only_what_it_is_given(q1, capsys):
    _, antes = envelope(["query", "show", q1, "-f", "json"], capsys)
    code, body = envelope(["query", "update", q1, "--favorite", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "q1", "updated": True}
    _, depois = envelope(["query", "show", q1, "-f", "json"], capsys)
    assert antes["data"]["is_favorite"] is False
    assert depois["data"]["is_favorite"] is True
    for campo in ("description", "folder", "sql", "connection", "created_at"):
        assert depois["data"][campo] == antes["data"][campo]


# QA-CONN-015
def test_query_list_filters_by_connection(q1, capsys):
    code, body = envelope(["query", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == [{"name": "q1", "connection": "local", "folder": "f", "description": "d", "params": []}]
    code, body = envelope(["query", "list", "--connection", "nope", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == []


# QA-CONN-016
def test_query_rm_needs_yes_off_a_tty(q1, capsys):
    code, body = envelope(["query", "rm", q1, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    code, _ = envelope(["query", "show", q1, "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["query", "rm", q1, "--yes", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "q1", "removed": True}
    code, body = envelope(["query", "show", q1, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Consulta "q1" nao encontrada.'


# --- group ---------------------------------------------------------------

@pytest.fixture
def g1(local, capsys) -> str:
    for nome in ("qa", "qb"):
        code, _ = envelope(
            ["query", "add", nome, "--connection", "local", "--sql", "SELECT id FROM clientes", "-f", "json"], capsys,
        )
        assert code == 0
    code, body = envelope(
        ["group", "add", "g1", "--query", "qa", "--query", "qb", "--join-key", "id",
         "--description", "gd", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "g1", "created": True}
    return "g1"


# QA-CONN-017
def test_group_add_then_show(g1, capsys):
    code, body = envelope(["group", "show", g1, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "group.show"
    assert body["data"]["queries"] == ["qa", "qb"]
    assert body["data"]["join_key"] == "id"
    assert body["data"]["description"] == "gd"


# QA-CONN-018
def test_group_add_refuses_a_duplicate(g1, capsys):
    code, body = envelope(["group", "add", g1, "--query", "qa", "--query", "qb", "--join-key", "id", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Grupo "g1" ja existe.'


# QA-CONN-019
def test_group_update_changes_only_what_it_is_given(g1, capsys):
    _, antes = envelope(["group", "show", g1, "-f", "json"], capsys)
    code, body = envelope(["group", "update", g1, "--folder", "pasta", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "g1", "updated": True}
    _, depois = envelope(["group", "show", g1, "-f", "json"], capsys)
    assert antes["data"]["folder"] == ""
    assert depois["data"]["folder"] == "pasta"
    for campo in ("description", "queries", "join_key", "created_at"):
        assert depois["data"][campo] == antes["data"][campo]


# QA-CONN-020
def test_group_list_shows_the_summary(g1, capsys):
    code, body = envelope(["group", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == [{"name": "g1", "description": "gd", "folder": "", "queries": ["qa", "qb"], "join_key": "id"}]


# QA-CONN-021
def test_group_rm_needs_yes_off_a_tty(g1, capsys):
    code, body = envelope(["group", "rm", g1, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    code, _ = envelope(["group", "show", g1, "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["group", "rm", g1, "--yes", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "g1", "removed": True}
    code, body = envelope(["group", "show", g1, "-f", "json"], capsys)
    assert code == 2 and body["error"]["code"] == "not_found"
