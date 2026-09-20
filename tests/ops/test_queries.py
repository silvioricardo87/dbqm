"""Saved queries through ops/, measured against `dbqm run -f json`."""
from __future__ import annotations

from dataclasses import replace

import pytest

from dbqm.cli import run_cli
from dbqm.models.query import load_queries, save_queries
from dbqm.ops import catalogue, deps, queries
from dbqm.ops.errors import OperationError
from tests.ops.conftest import envelope


@pytest.fixture
def saved(local_db, capsys):
    run_cli(["query", "add", "by-id", "--sql", "SELECT name FROM customers WHERE id = :id",
             "--connection", "local", "-f", "json"])
    capsys.readouterr()


def test_run_query_matches_the_cli(saved, capsys):
    _, body = envelope(["run", "by-id", "-p", "id=1", "-f", "json"], capsys)
    result = queries.run_query("by-id", {"id": "1"}).to_dict()
    # `elapsed` is a real wall-clock measurement of its own query; the CLI's
    # call and this one each measure their own, so only the rest is expected
    # to match bit for bit.
    result.pop("elapsed")
    expected = {k: v for k, v in body["data"].items() if k != "elapsed"}
    assert result == expected


def test_run_query_records_history(saved, capsys):
    queries.run_query("by-id", {"id": "1"})
    _, body = envelope(["history", "-f", "json"], capsys)
    assert body["data"][0]["name"] == "by-id"


def test_unknown_query_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        queries.run_query("nope", {})
    assert e.value.code == "not_found"


def test_undeclared_parameter_is_validation(saved):
    with pytest.raises(OperationError) as e:
        queries.run_query("by-id", {"id": "1", "zzz": "2"})
    assert e.value.code == "validation"


def test_missing_parameter_is_validation(saved):
    with pytest.raises(OperationError) as e:
        queries.run_query("by-id", {})
    assert e.value.code == "validation"


def test_connection_override_goes_through_the_resolver(saved, local2_db):
    seen = []

    def resolve(name):
        seen.append(name)
        return catalogue.connection(name)

    queries.run_query("by-id", {"id": "1"}, connection="local2", resolve=resolve)
    assert seen == ["local2"]


def test_the_connection_the_resolver_returns_is_the_one_used(saved, local2_db):
    """The seam the MCP policy uses: whatever the resolver hands back is
    what runs, name notwithstanding."""
    result = queries.run_query(
        "by-id", {"id": "1"},
        resolve=lambda name: replace(catalogue.connection("local2"), name="local2"),
    )
    assert result.connection_name == "local2"


def test_effective_params_fills_a_default_and_lets_an_explicit_value_win(saved):
    """A default has no `query add` flag -- only the TUI's query-manage
    screen sets one -- so it is written directly through the model, the way
    3066de6 did for a group's `shared_params`.
    """
    all_queries = load_queries()
    for q in all_queries:
        if q.name == "by-id":
            q.params[0].default = "1"
    save_queries(all_queries)

    query = deps.find_query("by-id")
    assert queries.effective_params(query, {}) == {"id": "1"}
    assert queries.effective_params(query, {"id": "2"}) == {"id": "2"}


def test_a_saved_query_that_is_not_a_select_is_usage(local_db, capsys):
    """`execute_query` refuses anything but a SELECT with `error_kind="usage"`
    before any driver is involved; the token must survive the move."""
    run_cli(["query", "add", "wipe", "--sql", "DELETE FROM orders", "--connection", "local", "-f", "json"])
    capsys.readouterr()
    with pytest.raises(OperationError) as e:
        queries.run_query("wipe", {})
    assert e.value.code == "usage"
