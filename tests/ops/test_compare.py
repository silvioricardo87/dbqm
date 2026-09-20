"""Comparisons through ops/, measured against `multi` and `run-group -f json`."""
from __future__ import annotations

from dataclasses import replace

import pytest

from dbqm.cli import run_cli
from dbqm.ops import catalogue, compare
from dbqm.ops.errors import OperationError
from tests.ops.conftest import envelope

SQL = "SELECT id, value FROM orders ORDER BY id"


def test_multi_matches_the_cli_and_diverges(local2_db, capsys):
    code, body = envelope(["multi", SQL, "-c", "local", "-c", "local2", "-f", "json"], capsys)
    assert code == 5
    c = compare.multi(SQL, ["local", "local2"], {}, key=None)
    assert c.group_result.all_match is False
    assert c.join_key == body["data"]["join_key"]
    assert compare.comparison_data(c) == body["data"]["comparisons"]
    assert list(c.results) == ["local", "local2"]


def test_multi_refuses_one_connection(local_db):
    with pytest.raises(OperationError) as e:
        compare.multi(SQL, ["local"], {}, key=None)
    assert e.value.code == "usage"


def test_multi_refuses_a_repeated_connection(local_db):
    with pytest.raises(OperationError) as e:
        compare.multi(SQL, ["local", "local"], {}, key=None)
    assert e.value.code == "usage"


def test_multi_refuses_a_statement_that_returns_nothing(local2_db):
    with pytest.raises(OperationError) as e:
        compare.multi("DELETE FROM orders", ["local", "local2"], {}, key=None)
    assert e.value.code == "usage"


def test_multi_unknown_connection_is_not_found_before_anything_runs(local_db):
    with pytest.raises(OperationError) as e:
        compare.multi(SQL, ["local", "nope"], {}, key=None)
    assert e.value.code == "not_found"


def test_multi_key_not_common_is_validation(local2_db):
    with pytest.raises(OperationError) as e:
        compare.multi(SQL, ["local", "local2"], {}, key="zzz")
    assert e.value.code == "validation"


def test_multi_resolves_every_name_through_the_resolver(local2_db):
    seen = []

    def resolve(name):
        seen.append(name)
        return catalogue.connection(name)

    compare.multi(SQL, ["local", "local2"], {}, key=None, resolve=resolve)
    assert seen == ["local", "local2"]


@pytest.fixture
def saved_group(local2_db, capsys):
    run_cli(["query", "add", "o1", "--sql", SQL, "--connection", "local", "-f", "json"])
    run_cli(["query", "add", "o2", "--sql", SQL, "--connection", "local2", "-f", "json"])
    run_cli(["group", "add", "g", "--query", "o1", "--query", "o2", "--join-key", "id", "-f", "json"])
    run_cli(["group", "add", "adhoc", "--adhoc-sql", SQL, "--connection", "local",
             "--connection", "local2", "-f", "json"])
    capsys.readouterr()


def test_run_group_saved_shape_matches_the_cli(saved_group, capsys):
    code, body = envelope(["run-group", "g", "-f", "json"], capsys)
    assert code == 5
    c = compare.run_group("g", {})
    assert c.join_key is None
    assert c.group_result.group_name == "g"
    assert compare.comparison_data(c) == body["data"]["comparisons"]


def test_run_group_adhoc_shape_matches_the_cli(saved_group, capsys):
    _, body = envelope(["run-group", "adhoc", "-f", "json"], capsys)
    c = compare.run_group("adhoc", {})
    assert c.join_key == body["data"]["join_key"]
    assert c.group_result.group_name == "adhoc"
    assert compare.comparison_data(c) == body["data"]["comparisons"]


def test_run_group_records_history(saved_group, capsys):
    compare.run_group("g", {})
    _, body = envelope(["history", "-f", "json"], capsys)
    assert body["data"][0]["name"] == "g"
    assert body["data"][0]["all_match"] is False


def test_run_group_unknown_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        compare.run_group("nope", {})
    assert e.value.code == "not_found"


def test_run_group_adhoc_goes_through_the_resolver(saved_group):
    seen = []

    def resolve(name):
        seen.append(name)
        return catalogue.connection(name)

    compare.run_group("adhoc", {}, resolve=resolve)
    assert seen == ["local", "local2"]


def test_run_group_saved_goes_through_the_resolver_for_each_query(saved_group):
    seen = []

    def resolve(name):
        seen.append(name)
        return replace(catalogue.connection(name), read_only=True)

    compare.run_group("g", {}, resolve=resolve)
    assert seen == ["local", "local2"]
