"""Tests for the UI-agnostic group rules."""
from __future__ import annotations

from dbqm.core.group_builder import build, upsert, validate
from dbqm.models.connection import Connection, save_connections
from dbqm.models.group import Group, load_groups
from dbqm.models.query import Query, save_queries


def _seed_connection(name: str = "c1") -> None:
    save_connections([Connection(name=name, db_type="mysql", user="u", password="")])


def _seed_queries(*names: str) -> None:
    _seed_connection()
    save_queries([Query(name=n, connection="c1", sql="SELECT 1") for n in names])


def test_validate_names_every_empty_required_field(tmp_config_dir):
    errors = validate({"name": "", "queries": [], "join_key": ""})
    assert any("nome" in e.lower() for e in errors)
    assert any("consultas" in e.lower() for e in errors)
    assert any("juncao" in e.lower() for e in errors)


def test_validate_requires_at_least_two_queries(tmp_config_dir):
    """One query compares nothing -- the same reasoning that makes
    `dbqm multi` require two connections."""
    _seed_queries("q1")
    errors = validate({"name": "g", "queries": ["q1"], "join_key": "id"})
    assert any("2 consultas" in e for e in errors)


def test_validate_rejects_a_query_that_does_not_exist(tmp_config_dir):
    """A group pointing at a query nobody created is a run that fails
    later, for a reason we could name now."""
    _seed_queries("q1")
    errors = validate({"name": "g", "queries": ["q1", "fantasma"], "join_key": "id"})
    assert any("fantasma" in e for e in errors)


def test_validate_accepts_queries_that_exist(tmp_config_dir):
    """The companion to the rejection above: proves the guard actually
    looks each name up rather than always failing (or always passing)."""
    _seed_queries("q1", "q2")
    errors = validate({"name": "g", "queries": ["q1", "q2"], "join_key": "id"})
    assert errors == []


def test_build_creates_a_group_from_values(tmp_config_dir):
    g = build({
        "name": "g", "description": "desc", "queries": ["q1", "q2"],
        "join_key": "id", "compare_columns": ["nome"],
    })
    assert g.name == "g"
    assert g.description == "desc"
    assert g.queries == ["q1", "q2"]
    assert g.join_key == "id"
    assert g.compare_columns == ["nome"]


def test_build_from_existing_preserves_what_values_omit(tmp_config_dir):
    """The rule this module exists for. A CLI `update` that sets one field
    must not erase the ones the TUI authored. Checked field by field, by
    name -- a round trip through to_dict() would pass even if both sides
    dropped the same field."""
    old = Group(
        name="g", description="old", queries=["q1", "q2"], join_key="id",
        compare_columns=["nome"],
        shared_params={"p": {"description": "d", "default": "1"}},
        column_mapping={"nome": {"q2": "nome2"}},
        normalize={"nome": {"ATIVO": "A"}},
        validation_rule="any_diff",
        folder="Relatorios",
        template="tpl1",
        template_fields={"titulo": "literal:Teste"},
        adhoc_sql="",
        connections=["c1", "c2"],
        created_at="2020-01-01T00:00:00",
    )
    new = build({"name": "g", "description": "nova"}, existing=old)

    assert new.queries == ["q1", "q2"]
    assert new.join_key == "id"
    assert new.compare_columns == ["nome"]
    assert new.shared_params == {"p": {"description": "d", "default": "1"}}
    assert new.column_mapping == {"nome": {"q2": "nome2"}}
    assert new.normalize == {"nome": {"ATIVO": "A"}}
    assert new.validation_rule == "any_diff"
    assert new.folder == "Relatorios"
    assert new.template == "tpl1"
    assert new.template_fields == {"titulo": "literal:Teste"}
    assert new.adhoc_sql == ""
    assert new.connections == ["c1", "c2"]
    assert new.created_at == "2020-01-01T00:00:00"
    assert new.description == "nova"


def test_build_never_mutates_existing(tmp_config_dir):
    old = Group(
        name="g", description="d", queries=["q1", "q2"], join_key="id",
        folder="A",
        shared_params={"p": {"default": "1"}},
        column_mapping={"nome": {"q2": "nome2"}},
        normalize={"nome": {"ATIVO": "A"}},
    )
    new = build({"name": "g", "folder": "B"}, existing=old)
    assert old.folder == "A"

    # `shared_params`, `column_mapping` and `normalize` are dicts of
    # dicts; a shallow copy would still let a write through the new
    # object reach the one that is supposedly untouched.
    new.shared_params["p"]["default"] = "2"
    assert old.shared_params["p"]["default"] == "1"

    new.column_mapping["nome"]["q2"] = "outra"
    assert old.column_mapping["nome"]["q2"] == "nome2"

    new.normalize["nome"]["ATIVO"] = "X"
    assert old.normalize["nome"]["ATIVO"] == "A"


def test_upsert_creates_then_replaces(tmp_config_dir):
    _seed_queries("q1", "q2")
    _, created = upsert({"name": "g", "queries": ["q1", "q2"], "join_key": "id"})
    assert created is True
    _, created = upsert({"name": "g", "queries": ["q1", "q2"], "join_key": "codigo"})
    assert created is False
    groups = load_groups()
    assert len(groups) == 1
    assert groups[0].join_key == "codigo"
