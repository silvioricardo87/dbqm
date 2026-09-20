"""The policy, without a server: what the resolver returns and what a listing shows."""
from __future__ import annotations

import pytest

from dbqm.mcp import policy
from dbqm.mcp.options import ServerOptions
from dbqm.models.group import Group
from dbqm.models.query import Query
from dbqm.ops import catalogue
from dbqm.ops.errors import OperationError


def test_default_options_force_read_only(local_db):
    conn = policy.resolver(ServerOptions())("local")
    assert conn.read_only is True
    # Transient: the stored connection is untouched.
    assert catalogue.connection("local").read_only is False


def test_allow_write_keeps_the_stored_flag(local_db, read_only_db):
    resolve = policy.resolver(ServerOptions(allow_write=True))
    assert resolve("local").read_only is False
    assert resolve("ro").read_only is True


def test_a_name_outside_the_allowlist_is_not_found(local2_db):
    resolve = policy.resolver(ServerOptions(connections=frozenset({"local"})))
    assert resolve("local").name == "local"
    with pytest.raises(OperationError) as e:
        resolve("local2")
    assert e.value.code == "not_found"


def test_an_unknown_name_is_not_found_too(local_db):
    with pytest.raises(OperationError) as e:
        policy.resolver(ServerOptions())("nope")
    assert e.value.code == "not_found"


def test_visible_filters_and_reports_the_effective_flag(local2_db):
    items = [catalogue.connection_summary(c) for c in catalogue.connections()]
    shown = policy.visible(ServerOptions(connections=frozenset({"local2"})), items)
    assert [i["name"] for i in shown] == ["local2"]
    assert shown[0]["read_only"] is True
    shown = policy.visible(ServerOptions(allow_write=True), items)
    assert {i["name"] for i in shown} == {"local", "local2"}
    assert all(i["read_only"] is False for i in shown)


def test_exposed_names(local_db):
    assert policy.exposed_names(ServerOptions()) is None
    assert policy.exposed_names(ServerOptions(connections=frozenset({"b", "a"}))) == ["a", "b"]


def _query(name: str, connection: str) -> Query:
    return Query(name=name, connection=connection, sql="SELECT 1")


def _group(name: str, *, queries: tuple[str, ...] = (), connections: tuple[str, ...] = ()) -> Group:
    return Group(name=name, description="", queries=list(queries), join_key="id",
                connections=list(connections))


def test_visible_queries_no_allowlist_is_everything():
    queries = [_query("q1", "local"), _query("q2", "local2")]
    assert policy.visible_queries(ServerOptions(), queries) == queries


def test_visible_queries_scoped_to_the_allowlist():
    queries = [_query("q1", "local"), _query("q2", "local2")]
    shown = policy.visible_queries(ServerOptions(connections=frozenset({"local"})), queries)
    assert [q.name for q in shown] == ["q1"]


def test_visible_groups_no_allowlist_is_everything():
    groups = [_group("g1", connections=["local", "local2"]), _group("g2", queries=["q1"])]
    assert policy.visible_groups(ServerOptions(), groups, []) == groups


def test_visible_groups_ad_hoc_hidden_when_a_connection_is_not_exposed():
    groups = [_group("g1", connections=["local", "local2"])]
    shown = policy.visible_groups(ServerOptions(connections=frozenset({"local"})), groups, [])
    assert shown == []


def test_visible_groups_saved_hidden_when_a_query_is_not_visible():
    queries = [_query("q1", "local"), _query("q2", "local2")]
    groups = [_group("g1", queries=["q1", "q2"]), _group("g2", queries=["q1"])]
    shown = policy.visible_groups(ServerOptions(connections=frozenset({"local"})), groups, queries)
    assert [g.name for g in shown] == ["g2"]
