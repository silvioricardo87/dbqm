"""docs/qa/settings.md — `config list|get|set` against a real settings
file under the temp config directory."""
from __future__ import annotations

from dataclasses import fields

from dbqm.models.settings import Settings
from tests.functional.conftest import envelope

CHAVES = [f.name for f in fields(Settings)]


# QA-CFG-001
def test_list_returns_every_key_with_its_default(tmp_config_dir, capsys):
    code, body = envelope(["config", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "config.list"
    assert list(body["data"]) == CHAVES
    assert body["data"]["audit_log_enabled"] is False
    assert body["data"]["theme"] == "plano-escuro"
    assert body["data"]["create_export_subdirs"] is True


# QA-CFG-002
def test_set_a_bool_then_get_returns_a_real_bool(tmp_config_dir, capsys):
    code, body = envelope(["config", "set", "audit_log_enabled", "true", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"key": "audit_log_enabled", "value": True}
    code, body = envelope(["config", "get", "audit_log_enabled", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["value"] is True


# QA-CFG-003
def test_a_bad_value_is_refused_and_the_old_one_stays(tmp_config_dir, capsys):
    code, _ = envelope(["config", "set", "audit_log_enabled", "true", "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["config", "set", "audit_log_enabled", "talvez", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == (
        'Valor invalido para "audit_log_enabled": "talvez". Use true/false, 1/0 ou sim/nao.'
    )
    _, body = envelope(["config", "get", "audit_log_enabled", "-f", "json"], capsys)
    assert body["data"]["value"] is True


# QA-CFG-004
def test_an_unknown_key_names_the_valid_ones(tmp_config_dir, capsys):
    code, body = envelope(["config", "set", "nao_existe", "1", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == (
        'Chave "nao_existe" nao existe. Chaves validas: ' + ", ".join(CHAVES) + "."
    )


# QA-CFG-005
def test_a_theme_that_does_not_exist_is_refused(tmp_config_dir, capsys):
    code, body = envelope(["config", "set", "theme", "inexistente", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Tema "inexistente" nao existe. Temas validos: plano-claro, plano-escuro.'


# QA-CFG-006
def test_get_of_an_unknown_key_is_not_found(tmp_config_dir, capsys):
    code, body = envelope(["config", "get", "nao_existe", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"


# QA-CFG-007
def test_set_a_string_changes_only_that_key(tmp_config_dir, capsys):
    _, antes = envelope(["config", "list", "-f", "json"], capsys)
    code, body = envelope(["config", "set", "theme", "plano-claro", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"key": "theme", "value": "plano-claro"}
    _, depois = envelope(["config", "list", "-f", "json"], capsys)
    assert depois["data"]["theme"] == "plano-claro"
    assert {k: v for k, v in depois["data"].items() if k != "theme"} == {
        k: v for k, v in antes["data"].items() if k != "theme"
    }
