"""What is configured, as the CLI reports it -- measured against `-f json`."""
from __future__ import annotations

from dataclasses import replace

import pytest

from dbqm.ops import catalogue
from dbqm.ops.errors import OperationError
from tests.ops.conftest import envelope


def test_connection_resolves_a_name(local_db):
    assert catalogue.connection("local").name == "local"


def test_connection_raises_not_found_for_an_unknown_name(local_db):
    with pytest.raises(OperationError) as e:
        catalogue.connection("nope")
    assert e.value.code == "not_found"


def test_connection_summaries_are_what_list_emits(local_db, capsys):
    _, body = envelope(["list", "connections", "-f", "json"], capsys)
    assert [catalogue.connection_summary(c) for c in catalogue.connections()] == body["data"]


def test_query_and_group_summaries_are_what_list_emits(local_db, capsys):
    from dbqm.cli import run_cli
    run_cli(["query", "add", "q1", "--sql", "SELECT 1", "--connection", "local", "-f", "json"])
    # A group needs at least two distinct saved queries (`group_builder.validate`).
    run_cli(["query", "add", "q2", "--sql", "SELECT 2", "--connection", "local", "-f", "json"])
    run_cli(["group", "add", "g1", "--query", "q1", "--query", "q2", "--join-key", "id", "-f", "json"])
    capsys.readouterr()
    _, queries = envelope(["list", "queries", "-f", "json"], capsys)
    _, groups = envelope(["list", "groups", "-f", "json"], capsys)
    assert [catalogue.query_summary(q) for q in catalogue.queries()] == queries["data"]
    assert [catalogue.group_summary(g) for g in catalogue.groups()] == groups["data"]


def test_test_connections_reports_each_and_never_raises_for_a_down_one(broken_db, local_db):
    data = catalogue.test_connections(None)
    by_name = {d["name"]: d for d in data}
    assert by_name["local"]["ok"] is True
    assert by_name["broken"]["ok"] is False
    assert set(by_name["broken"]) == {"name", "ok", "message"}


def test_test_connections_with_no_names_applies_a_given_resolver_to_every_stored_one(local_db, local2_db):
    seen = []

    def resolve(name):
        seen.append(name)
        return replace(catalogue.connection(name), read_only=True)

    data = catalogue.test_connections(None, resolve=resolve)
    assert sorted(seen) == ["local", "local2"]
    assert all(d["ok"] for d in data)


def test_test_connections_by_name_goes_through_the_resolver(local_db):
    seen = []

    def resolve(name):
        seen.append(name)
        return replace(catalogue.connection(name), read_only=True)

    data = catalogue.test_connections(["local"], resolve=resolve)
    assert seen == ["local"]
    assert data[0]["ok"] is True


def test_test_connections_unknown_name_is_not_found(local_db):
    with pytest.raises(OperationError) as e:
        catalogue.test_connections(["nope"])
    assert e.value.code == "not_found"


def test_history_refuses_a_non_positive_limit(local_db):
    with pytest.raises(OperationError) as e:
        catalogue.history(0)
    assert e.value.code == "usage"


def test_history_is_what_the_cli_emits(local_db, capsys):
    from dbqm.cli import run_cli
    run_cli(["query", "add", "q1", "--sql", "SELECT 1", "--connection", "local", "-f", "json"])
    run_cli(["run", "q1", "-f", "json"])
    capsys.readouterr()
    _, body = envelope(["history", "-f", "json"], capsys)
    assert [e.to_dict() for e in catalogue.history(None)] == body["data"]
