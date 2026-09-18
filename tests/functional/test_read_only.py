"""docs/qa/read-only-guard.md — a read-only connection, refused and lifted.

`ro` and `local` are the same SQLite file, so "nothing changed" is read
back through `local` after every refusal rather than assumed.
"""
from __future__ import annotations

import pytest

from tests.functional.conftest import envelope

REFUSAL = "Connection 'ro' is read-only. Use --force-write to send it anyway."


def _status_of_1(capsys) -> str:
    code, body = envelope(["sql", "SELECT status FROM clientes WHERE id = 1", "local", "-f", "json"], capsys)
    assert code == 0
    return body["data"]["rows"][0][0]


def _tables(capsys) -> list[str]:
    code, body = envelope(["objects", "local", "--type", "TABLE", "-f", "json"], capsys)
    assert code == 0
    return body["data"]["objects"]


# QA-RO-001
def test_an_update_is_refused_and_nothing_changes(read_only_db, capsys):
    code, body = envelope(["sql", "UPDATE clientes SET status='X' WHERE id=1", "ro", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "read_only"
    assert body["error"]["message"] == REFUSAL
    assert _status_of_1(capsys) == "A"


# QA-RO-002
def test_force_write_lifts_the_guard_for_one_call(read_only_db, capsys):
    code, body = envelope(
        ["sql", "UPDATE clientes SET status='X' WHERE id=1", "ro", "--force-write", "--commit", "-f", "json"],
        capsys,
    )
    assert code == 0
    assert body["data"]["rows_affected"] == 1
    assert _status_of_1(capsys) == "X"
    # one call: the next write on `ro` is refused again -- the override was
    # never saved
    code, body = envelope(["sql", "UPDATE clientes SET status='A' WHERE id=1", "ro", "--commit", "-f", "json"], capsys)
    assert code == 2 and body["error"]["code"] == "read_only"


# QA-RO-003
def test_a_select_passes(read_only_db, capsys):
    code, body = envelope(["sql", "SELECT nome FROM clientes WHERE id=1", "ro", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["rows"] == [["Ana"]]


# QA-RO-004
def test_explain_passes(read_only_db, capsys):
    code, body = envelope(["sql", "SELECT id FROM clientes", "ro", "--explain", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["plan"]


# QA-RO-005
def test_a_hand_written_explain_query_plan_passes(read_only_db, capsys):
    """SQLite's native `EXPLAIN QUERY PLAN` only reads. Before 2.9.0 the
    guard did not know the `QUERY PLAN` prefix and refused it as an EXPLAIN
    that executes -- found by this scenario."""
    code, body = envelope(["sql", "EXPLAIN QUERY PLAN SELECT id FROM clientes", "ro", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["rows"]


# QA-RO-006
def test_two_statements_are_refused_by_count(read_only_db, capsys):
    code, body = envelope(["sql", "SELECT 1; DROP TABLE clientes", "ro", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "read_only"
    assert "more than one statement" in body["error"]["message"]
    assert "clientes" in _tables(capsys)


# QA-RO-007
@pytest.mark.parametrize("sql", [
    "INSERT INTO clientes VALUES (4, 'Dora', 'A')",
    "DELETE FROM clientes WHERE id = 1",
    "CREATE TABLE intruso (id INTEGER)",
    "DROP TABLE pedidos",
])
def test_every_write_verb_is_refused(read_only_db, capsys, sql):
    code, body = envelope(["sql", sql, "ro", "--commit", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "read_only"
    assert body["error"]["message"] == REFUSAL
    code, contagem = envelope(["sql", "SELECT COUNT(*) FROM clientes", "local", "-f", "json"], capsys)
    assert contagem["data"]["rows"] == [[3]]
    assert sorted(_tables(capsys)) == ["clientes", "pedidos"]


# QA-RO-008
def test_the_read_only_refusal_comes_before_the_commit_one(read_only_db, capsys):
    """Without `--commit` a writable connection says `usage`; on `ro` the
    guard answers first, so the user meets the real obstacle in one trip."""
    code, body = envelope(["sql", "UPDATE clientes SET status='X' WHERE id=1", "ro", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "read_only"


# QA-RO-009
def test_force_write_on_a_writable_connection_changes_nothing(local_db, capsys):
    code, body = envelope(
        ["sql", "UPDATE clientes SET status='X' WHERE id=1", "local", "--force-write", "--commit", "-f", "json"],
        capsys,
    )
    assert code == 0
    assert body["data"]["rows_affected"] == 1


# QA-RO-010
def test_run_of_a_writing_query_is_refused(read_only_db, capsys):
    """`run` has no write path at all: `execute_query` accepts only SELECT,
    on any connection, so the refusal is `usage` and comes before the
    read-only guard would have spoken. Either way nothing is sent."""
    code, _ = envelope(
        ["query", "add", "atualiza", "--connection", "local",
         "--sql", "UPDATE clientes SET status='X' WHERE id=1", "-f", "json"],
        capsys,
    )
    assert code == 0
    code, body = envelope(["run", "atualiza", "-c", "ro", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Only SELECT statements are allowed."
    assert _status_of_1(capsys) == "A"
