"""docs/qa/groups.md — `group add` then `run-group`, over two real files.

`local` and `local2` are the same schema; pedido 13 is the one row that
differs. So `clientes` agrees, `pedidos` diverges, and both verdicts are
produced by the data, not by a mock.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.functional.conftest import envelope, invoke

ORDERS = "SELECT id, valor FROM pedidos ORDER BY id"
CLI = "SELECT id, nome FROM clientes ORDER BY id"


def _add_query(name: str, conn: str, sql: str, capsys) -> None:
    code, _ = envelope(["query", "add", name, "--connection", conn, "--sql", sql, "-f", "json"], capsys)
    assert code == 0


@pytest.fixture
def pedidos(local2_db, capsys) -> str:
    """The group that diverges: 4 keys, 3 equal, 1 different on `valor`."""
    _add_query("ped_local", "local", ORDERS, capsys)
    _add_query("ped_local2", "local2", ORDERS, capsys)
    code, body = envelope(
        ["group", "add", "pedidos", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "pedidos", "created": True}
    return "pedidos"


@pytest.fixture
def clientes(local2_db, capsys) -> str:
    """The group that agrees."""
    _add_query("cli_local", "local", CLI, capsys)
    _add_query("cli_local2", "local2", CLI, capsys)
    code, body = envelope(
        ["group", "add", "clientes", "--query", "cli_local", "--query", "cli_local2",
         "--join-key", "id", "--compare-column", "nome", "-f", "json"],
        capsys,
    )
    assert code == 0 and body["data"] == {"name": "clientes", "created": True}
    return "clientes"


# QA-GROUP-001
def test_group_add_then_run_group_that_agrees(clientes, capsys):
    code, body = envelope(["run-group", clientes, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "run-group"
    assert body["data"]["group"] == "clientes"
    assert body["data"]["all_match"] is True
    assert body["data"]["comparisons"] == [{
        "column": "nome", "total_keys": 3, "equal_count": 3,
        "diff_count": 0, "absent_count": 0, "normalized_count": 0,
        "duplicate_rows": {},
    }]


# QA-GROUP-002, QA-OUT-014
def test_a_real_divergence_exits_5(pedidos, capsys):
    code, out, err = invoke(["run-group", pedidos, "-f", "json"], capsys)
    assert code == 5
    assert err == ""
    body = json.loads(out)
    assert body["ok"] is True
    assert body["data"]["all_match"] is False
    assert body["data"]["comparisons"] == [{
        "column": "valor", "total_keys": 4, "equal_count": 3,
        "diff_count": 1, "absent_count": 0, "normalized_count": 0,
        "duplicate_rows": {},
    }]


# QA-GROUP-003
def test_table_format_prints_the_verdict_with_the_same_exit(pedidos, clientes, capsys):
    code, out, _ = invoke(["run-group", pedidos], capsys)
    assert code == 5
    assert "DIVERGENT" in out
    code, out, _ = invoke(["run-group", clientes], capsys)
    assert code == 0
    assert "CONSISTENT" in out


# QA-GROUP-004
def test_export_html_still_exits_5_after_writing(pedidos, tmp_path, capsys):
    code, body = envelope(["run-group", pedidos, "-e", "html", "-f", "json"], capsys)
    assert code == 5
    assert body["ok"] is True
    assert body["data"]["format"] == "html"
    exported = Path(body["data"]["exported"])
    assert exported.suffix == ".html"
    assert tmp_path in exported.parents
    assert "<table" in exported.read_text(encoding="utf-8")


# QA-GROUP-005
def test_flat_with_html_is_refused_before_anything_runs(pedidos, capsys):
    code, body = envelope(["run-group", pedidos, "--flat", "-e", "html", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"].startswith("--flat has no HTML version.")
    code, history = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    assert [e for e in history["data"] if e["entry_type"] == "group"] == []


# QA-GROUP-006
def test_flat_csv_writes_and_keeps_the_verdict(pedidos, capsys):
    code, body = envelope(["run-group", pedidos, "--flat", "-e", "csv", "-f", "json"], capsys)
    assert code == 5
    exported = Path(body["data"]["exported"])
    assert exported.name.startswith("flat_") and exported.suffix == ".csv"
    assert exported.is_file()


# QA-GROUP-007
def test_an_unknown_group_is_not_found(local_db, capsys):
    code, body = envelope(["run-group", "nope", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == 'Group "nope" not found.'


# QA-GROUP-008
def test_a_group_needs_two_queries(local_db, capsys):
    _add_query("cli_local", "local", CLI, capsys)
    code, body = envelope(["group", "add", "um", "--query", "cli_local", "--join-key", "id", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == "Choose at least 2 queries."


# QA-GROUP-009
def test_a_divergent_run_is_still_recorded_in_history(pedidos, capsys):
    code, _ = envelope(["run-group", pedidos, "-f", "json"], capsys)
    assert code == 5
    code, body = envelope(["history", "-f", "json"], capsys)
    assert code == 0
    records = [e for e in body["data"] if e["entry_type"] == "group"]
    assert len(records) == 1
    assert records[0]["name"] == "pedidos"
    assert records[0]["all_match"] is False


# QA-GROUP-010
def test_a_failing_query_names_itself(local2_db, capsys):
    _add_query("quebrada", "local", "SELECT * FROM nao_existe", capsys)
    _add_query("cli_local2", "local2", CLI, capsys)
    code, _ = envelope(
        ["group", "add", "quebrado", "--query", "quebrada", "--query", "cli_local2", "--join-key", "id", "-f", "json"],
        capsys,
    )
    assert code == 0
    code, body = envelope(["run-group", "quebrado", "-f", "json"], capsys)
    assert code == 4
    assert body["error"]["code"] == "sql_error"
    assert body["error"]["message"] == 'Error in query "quebrada": no such table: nao_existe'


BY_CLIENT = "SELECT cliente_id AS id, valor FROM pedidos ORDER BY id"


@pytest.fixture
def by_client(local2_db, capsys) -> str:
    """A group whose join key repeats: four pedidos over two clientes, so
    each side loses two rows to a key it had already seen."""
    _add_query("pc_local", "local", BY_CLIENT, capsys)
    _add_query("pc_local2", "local2", BY_CLIENT, capsys)
    code, _ = envelope(
        ["group", "add", "por_cliente", "--query", "pc_local", "--query", "pc_local2",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "por_cliente"


# QA-GROUP-011
def test_a_repeated_join_key_is_reported_not_swallowed(by_client, capsys):
    code, out, _ = invoke(["run-group", by_client, "-f", "json"], capsys)
    body = json.loads(out)
    assert body["warnings"] == [
        "Key 'id' has repeated values in 'pc_local': 2 row(s) left out of the comparison.",
        "Key 'id' has repeated values in 'pc_local2': 2 row(s) left out of the comparison.",
    ]
    assert body["data"]["comparisons"][0]["duplicate_rows"] == {"pc_local": 2, "pc_local2": 2}
    assert body["data"]["comparisons"][0]["total_keys"] == 2
    assert code == 5


# QA-GROUP-012
def test_a_unique_join_key_warns_about_nothing(pedidos, capsys):
    code, out, _ = invoke(["run-group", pedidos, "-f", "json"], capsys)
    body = json.loads(out)
    assert "warnings" not in body
    assert body["data"]["comparisons"][0]["duplicate_rows"] == {}
    assert code == 5


# QA-GROUP-013
def test_the_warning_reaches_the_table_format_too(by_client, capsys):
    code, out, _ = invoke(["run-group", by_client], capsys)
    assert code == 5
    assert "repeated values in 'pc_local'" in out


@pytest.fixture
def without_columns(local2_db, capsys) -> str:
    """A group that names no `--compare-column` -- the flag is optional, so
    this is the plain `group add` anyone would type."""
    _add_query("ped_local", "local", ORDERS, capsys)
    _add_query("ped_local2", "local2", ORDERS, capsys)
    code, _ = envelope(
        ["group", "add", "sem_colunas", "--query", "ped_local", "--query", "ped_local2",
         "--join-key", "id", "-f", "json"],
        capsys,
    )
    assert code == 0
    return "sem_colunas"


# QA-GROUP-017
def test_a_group_with_no_compare_columns_still_compares(without_columns, capsys):
    """It answered `all_match: true` with `comparisons: []` and exit 0 --
    CONSISTENT over data nothing had looked at, while the equivalent
    `multi` exited 5 on the same rows."""
    code, out, _ = invoke(["run-group", without_columns, "-f", "json"], capsys)
    body = json.loads(out)
    assert code == 5
    assert body["data"]["all_match"] is False
    assert [c["column"] for c in body["data"]["comparisons"]] == ["valor"]
    assert body["data"]["comparisons"][0]["diff_count"] == 1


# QA-GROUP-018
def test_deriving_the_columns_is_said_out_loud(without_columns, capsys):
    code, out, _ = invoke(["run-group", without_columns, "-f", "json"], capsys)
    assert code == 5
    assert json.loads(out)["warnings"][0] == (
        'Group "sem_colunas" does not define columns to compare; '
        'comparing the common ones: valor.'
    )


# QA-GROUP-019
def test_nothing_common_beyond_the_key_is_refused(local2_db, capsys):
    """Deriving cannot invent a column. With only the key in common there
    is nothing to compare, and a verdict would be vacuous."""
    _add_query("so_id_local", "local", "SELECT id FROM pedidos", capsys)
    _add_query("so_id_local2", "local2", "SELECT id FROM pedidos", capsys)
    code, _ = envelope(
        ["group", "add", "so_id", "--query", "so_id_local", "--query", "so_id_local2",
         "--join-key", "id", "-f", "json"],
        capsys,
    )
    assert code == 0
    code, body = envelope(["run-group", "so_id", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == (
        'Group "so_id" does not define columns to compare, and the queries have '
        'no column in common other than "id".'
    )


# QA-GROUP-020
def test_a_group_cannot_name_the_same_query_twice(local_db, capsys):
    """`run_comparison` keys its index by query name, so the same name
    twice collapses to one side and the comparison agrees with itself.
    `multi` refuses the same shape for a repeated `-c`."""
    _add_query("ped_local", "local", ORDERS, capsys)
    code, body = envelope(
        ["group", "add", "repetida", "--query", "ped_local", "--query", "ped_local",
         "--join-key", "id", "--compare-column", "valor", "-f", "json"],
        capsys,
    )
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == (
        'Query "ped_local" is repeated. A group compares distinct queries.'
    )
