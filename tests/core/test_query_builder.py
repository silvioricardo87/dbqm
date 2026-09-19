"""Tests for the UI-agnostic saved-query rules."""
from __future__ import annotations

from dbqm.core.query_builder import build, upsert, validate
from dbqm.models.connection import Connection, save_connections
from dbqm.models.query import Query, load_queries


def _seed_connection(name: str = "c1") -> None:
    save_connections([Connection(name=name, db_type="mysql", user="u", password="")])


def test_validate_names_every_empty_required_field(tmp_config_dir):
    errors = validate({"name": "", "connection": "", "sql": ""})
    assert any("name" in e.lower() for e in errors)
    assert any("sql" in e.lower() for e in errors)
    assert any("connection" in e.lower() for e in errors)


def test_validate_rejects_a_connection_that_does_not_exist(tmp_config_dir):
    """A saved query pointing at a connection nobody created is a run that
    fails later, for a reason we could name now."""
    errors = validate({"name": "q", "connection": "fantasma", "sql": "SELECT 1"})
    assert any("fantasma" in e for e in errors)


def test_validate_accepts_a_connection_that_exists(tmp_config_dir):
    """The companion to the rejection above: proves the guard actually
    looks the name up rather than always failing (or always passing)."""
    _seed_connection("c1")
    errors = validate({"name": "q", "connection": "c1", "sql": "SELECT 1"})
    assert errors == []


def test_build_derives_table_columns_and_params(tmp_config_dir):
    q = build({"name": "q", "connection": "c1",
               "sql": "SELECT ID, NAME FROM CUSTOMERS WHERE ID = :id ORDER BY NAME"})
    assert q.table == "CUSTOMERS"
    assert q.columns == ["id", "name"]
    assert q.order_by == "NAME"
    assert [p.name for p in q.params] == ["id"]


def test_build_from_existing_preserves_what_values_omit(tmp_config_dir):
    """The rule this module exists for. A CLI `update` that sets one field
    must not erase the ones the TUI authored."""
    old = Query(
        name="q", connection="c1", sql="SELECT 1",
        column_maps={"ST": {"A": "Ativo"}}, is_favorite=True,
        folder="Relatorios", created_at="2020-01-01T00:00:00",
        last_executed="2024-06-01T12:00:00",
    )
    new = build({"name": "q", "description": "nova"}, existing=old)
    assert new.column_maps == {"ST": {"A": "Ativo"}}
    assert new.is_favorite is True
    assert new.folder == "Relatorios"
    assert new.created_at == "2020-01-01T00:00:00"
    assert new.last_executed == "2024-06-01T12:00:00"
    assert new.description == "nova"
    assert new.sql == "SELECT 1"


def test_build_preserves_the_sql_derived_fields_when_sql_is_absent(tmp_config_dir):
    """`table`, `columns` and `order_by` come from parsing `sql`. When
    `values` does not touch `sql`, that parse must not be redone either --
    otherwise a hand-edited `table` (the screen's "Tabela" edit) would be
    silently overwritten by re-parsing SQL that never changed."""
    old = Query(
        name="q", connection="c1", sql="SELECT 1",
        table="TABELA_MANUAL", columns=["a", "b"], order_by="a",
    )
    new = build({"name": "q", "description": "nova"}, existing=old)
    assert new.table == "TABELA_MANUAL"
    assert new.columns == ["a", "b"]
    assert new.order_by == "a"


def test_build_never_mutates_existing(tmp_config_dir):
    old = Query(name="q", connection="c1", sql="SELECT 1", folder="A",
                column_maps={"ST": {"A": "Ativo"}})
    new = build({"name": "q", "folder": "B"}, existing=old)
    assert old.folder == "A"

    # `column_maps` is a dict of dicts; a shallow copy would still let a
    # write through the new object reach the one that is supposedly untouched.
    new.column_maps["ST"]["A"] = "Mudou"
    assert old.column_maps["ST"]["A"] == "Ativo"


def test_upsert_creates_then_replaces(tmp_config_dir):
    _, created = upsert({"name": "q", "connection": "c1", "sql": "SELECT 1"})
    assert created is True
    _, created = upsert({"name": "q", "connection": "c1", "sql": "SELECT 2"})
    assert created is False
    queries = load_queries()
    assert len(queries) == 1
    assert queries[0].sql == "SELECT 2"
