"""Tests for the UI-agnostic template rules."""
from __future__ import annotations

from dbqm.core.template_builder import build, upsert, validate
from dbqm.models.template import Template, load_templates


def test_validate_names_every_empty_required_field(tmp_config_dir):
    errors = validate({"name": "", "content": ""})
    assert any("nome" in e.lower() for e in errors)
    assert any("conteudo" in e.lower() for e in errors)


def test_validate_treats_whitespace_only_content_as_empty(tmp_config_dir):
    """`validate` checks the trimmed form -- a template made only of
    whitespace is exactly as useless as an empty one."""
    errors = validate({"name": "t", "content": "   \n  "})
    assert any("conteudo" in e.lower() for e in errors)


def test_validate_accepts_a_complete_template(tmp_config_dir):
    errors = validate({"name": "t", "content": "Ola {{nome}}"})
    assert errors == []


def test_build_creates_a_template_from_values(tmp_config_dir):
    t = build({"name": "t", "description": "desc", "content": "Ola {{nome}}"})
    assert t.name == "t"
    assert t.description == "desc"
    assert t.content == "Ola {{nome}}"


def test_build_from_existing_preserves_what_values_omit(tmp_config_dir):
    """The rule this module exists for. A CLI `update` that sets one field
    must not erase the ones the TUI authored. `created_at` is asserted
    against a value `build` could never reproduce on its own -- a fixed,
    made-up ISO string, not the field's own default -- so a regression that
    silently regenerates it cannot pass this by accident."""
    old = Template(
        name="t", description="old", content="Ola {{nome}}",
        created_at="2020-01-01T00:00:00",
    )
    new = build({"name": "t", "description": "nova"}, existing=old)
    assert new.content == "Ola {{nome}}"
    assert new.created_at == "2020-01-01T00:00:00"
    assert new.description == "nova"


def test_build_preserves_content_whitespace_verbatim(tmp_config_dir):
    """Unlike `name`/`description`, `content` is never `.strip()`-ed: a
    report template's leading/trailing blank lines are formatting, not
    incidental input noise."""
    t = build({"name": "t", "content": "  linha 1\n\nlinha 2  \n"})
    assert t.content == "  linha 1\n\nlinha 2  \n"


def test_build_never_mutates_existing(tmp_config_dir):
    old = Template(name="t", description="d", content="original")
    new = build({"name": "t", "description": "nova"}, existing=old)
    assert old.description == "d"
    assert old.content == "original"
    new.content = "mudou"
    assert old.content == "original"


def test_upsert_creates_then_replaces(tmp_config_dir):
    _, created = upsert({"name": "t", "content": "v1"})
    assert created is True
    _, created = upsert({"name": "t", "content": "v2"})
    assert created is False
    templates = load_templates()
    assert len(templates) == 1
    assert templates[0].content == "v2"
