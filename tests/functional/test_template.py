"""docs/qa/templates.md — the template verbs. No database: only the
config directory."""
from __future__ import annotations

import pytest

from tests.functional.conftest import envelope

CONTEUDO = "SELECT * FROM {{tabela}}"


@pytest.fixture
def t1(tmp_config_dir, capsys) -> str:
    code, body = envelope(["template", "add", "t1", "--content", CONTEUDO, "--description", "td", "-f", "json"], capsys)
    assert code == 0 and body["data"] == {"name": "t1", "created": True}
    return "t1"


# QA-TPL-001
def test_add_then_show(t1, capsys):
    code, body = envelope(["template", "show", t1, "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "template.show"
    assert body["data"]["content"] == CONTEUDO
    assert body["data"]["description"] == "td"


# QA-TPL-002
def test_add_refuses_a_duplicate_and_keeps_the_original(t1, capsys):
    code, body = envelope(["template", "add", t1, "--content", "x", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Template "t1" already exists.'
    _, body = envelope(["template", "show", t1, "-f", "json"], capsys)
    assert body["data"]["content"] == CONTEUDO


# QA-TPL-003
def test_content_file_is_read(tmp_config_dir, tmp_path, capsys):
    arquivo = tmp_path / "t2.sql"
    arquivo.write_text("SELECT {{coluna}}\nFROM {{tabela}}\n", encoding="utf-8")
    code, _ = envelope(["template", "add", "t2", "--content-file", str(arquivo), "-f", "json"], capsys)
    assert code == 0
    _, body = envelope(["template", "show", "t2", "-f", "json"], capsys)
    assert body["data"]["content"] == "SELECT {{coluna}}\nFROM {{tabela}}\n"


# QA-TPL-004
def test_update_changes_only_what_it_is_given(t1, capsys):
    code, body = envelope(["template", "update", t1, "--description", "nova", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "t1", "updated": True}
    _, body = envelope(["template", "show", t1, "-f", "json"], capsys)
    assert body["data"]["description"] == "nova"
    assert body["data"]["content"] == CONTEUDO


# QA-TPL-005
def test_update_of_an_unknown_name_is_not_found(tmp_config_dir, capsys):
    code, body = envelope(["template", "update", "nope", "--description", "x", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"


# QA-TPL-006
def test_list_shows_name_and_description(t1, capsys):
    code, body = envelope(["template", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == [{"name": "t1", "description": "td"}]


# QA-TPL-007
def test_rm_without_yes_off_a_tty_is_refused(t1, capsys):
    code, body = envelope(["template", "rm", t1, "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "usage"
    assert body["error"]["message"] == "Use --yes to remove without confirming."
    code, _ = envelope(["template", "show", t1, "-f", "json"], capsys)
    assert code == 0


# QA-TPL-008
def test_rm_with_yes_removes_it(t1, capsys):
    code, body = envelope(["template", "rm", t1, "--yes", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"name": "t1", "removed": True}
    code, body = envelope(["template", "show", t1, "-f", "json"], capsys)
    assert code == 2 and body["error"]["code"] == "not_found"
