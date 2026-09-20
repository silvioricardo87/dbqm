"""The policy, without a server: what the resolver returns and what a listing shows."""
from __future__ import annotations

import pytest

from dbqm.mcp import policy
from dbqm.mcp.options import ServerOptions
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
