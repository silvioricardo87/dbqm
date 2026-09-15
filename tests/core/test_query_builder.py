"""Tests for the UI-agnostic saved-query rules."""
from __future__ import annotations

from dbqm.core.query_builder import build, upsert, validate
from dbqm.models.query import Query, load_queries


def test_validate_names_every_empty_required_field(tmp_config_dir):
    errors = validate({"name": "", "connection": "", "sql": ""})
    assert any("nome" in e.lower() for e in errors)
    assert any("sql" in e.lower() for e in errors)
    assert any("conexao" in e.lower() for e in errors)


def test_validate_rejects_a_connection_that_does_not_exist(tmp_config_dir):
    """A saved query pointing at a connection nobody created is a run that
    fails later, for a reason we could name now."""
    errors = validate({"name": "q", "connection": "fantasma", "sql": "SELECT 1"})
    assert any("fantasma" in e for e in errors)


def test_build_derives_table_columns_and_params(tmp_config_dir):
    q = build({"name": "q", "connection": "c1",
               "sql": "SELECT ID, NOME FROM CLIENTES WHERE ID = :id"})
    assert q.table == "CLIENTES"
    assert [p.name for p in q.params] == ["id"]


def test_build_from_existing_preserves_what_values_omit(tmp_config_dir):
    """The rule this module exists for. A CLI `update` that sets one field
    must not erase the ones the TUI authored."""
    old = Query(
        name="q", connection="c1", sql="SELECT 1",
        column_maps={"ST": {"A": "Ativo"}}, is_favorite=True,
        folder="Relatorios", created_at="2020-01-01T00:00:00",
    )
    new = build({"name": "q", "description": "nova"}, existing=old)
    assert new.column_maps == {"ST": {"A": "Ativo"}}
    assert new.is_favorite is True
    assert new.folder == "Relatorios"
    assert new.created_at == "2020-01-01T00:00:00"
    assert new.description == "nova"
    assert new.sql == "SELECT 1"


def test_build_never_mutates_existing(tmp_config_dir):
    old = Query(name="q", connection="c1", sql="SELECT 1", folder="A")
    build({"name": "q", "folder": "B"}, existing=old)
    assert old.folder == "A"


def test_upsert_creates_then_replaces(tmp_config_dir):
    _, created = upsert({"name": "q", "connection": "c1", "sql": "SELECT 1"})
    assert created is True
    _, created = upsert({"name": "q", "connection": "c1", "sql": "SELECT 2"})
    assert created is False
    assert len(load_queries()) == 1
