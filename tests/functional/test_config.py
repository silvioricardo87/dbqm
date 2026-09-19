"""docs/qa/settings.md — `config list|get|set` against a real settings
file under the temp config directory."""
from __future__ import annotations

from dataclasses import fields

from dbqm.models.settings import Settings
from tests.functional.conftest import envelope

KEYS = [f.name for f in fields(Settings)]


# QA-CFG-001
def test_list_returns_every_key_with_its_default(tmp_config_dir, capsys):
    code, body = envelope(["config", "list", "-f", "json"], capsys)
    assert code == 0
    assert body["command"] == "config.list"
    assert list(body["data"]) == KEYS
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
        'Invalid value for "audit_log_enabled": "talvez". Use true/false, 1/0 or yes/no.'
    )
    _, body = envelope(["config", "get", "audit_log_enabled", "-f", "json"], capsys)
    assert body["data"]["value"] is True


# QA-CFG-004
def test_an_unknown_key_names_the_valid_ones(tmp_config_dir, capsys):
    code, body = envelope(["config", "set", "nao_existe", "1", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"
    assert body["error"]["message"] == (
        'Key "nao_existe" does not exist. Valid keys: ' + ", ".join(KEYS) + "."
    )


# QA-CFG-005
def test_a_theme_that_does_not_exist_is_refused(tmp_config_dir, capsys):
    code, body = envelope(["config", "set", "theme", "inexistente", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Theme "inexistente" does not exist. Valid themes: plano-claro, plano-escuro.'


# QA-CFG-006
def test_get_of_an_unknown_key_is_not_found(tmp_config_dir, capsys):
    code, body = envelope(["config", "get", "nao_existe", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "not_found"


# QA-CFG-007
def test_set_a_string_changes_only_that_key(tmp_config_dir, capsys):
    _, before = envelope(["config", "list", "-f", "json"], capsys)
    code, body = envelope(["config", "set", "theme", "plano-claro", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"key": "theme", "value": "plano-claro"}
    _, after = envelope(["config", "list", "-f", "json"], capsys)
    assert after["data"]["theme"] == "plano-claro"
    assert {k: v for k, v in after["data"].items() if k != "theme"} == {
        k: v for k, v in before["data"].items() if k != "theme"
    }


# QA-CFG-008
def test_the_language_is_stored_and_validated(tmp_config_dir, capsys):
    """Valid languages come from the catalogue at runtime, like themes come
    from the design tokens."""
    code, body = envelope(["config", "get", "language", "-f", "json"], capsys)
    assert code == 0
    assert body["data"]["value"] == "en"

    code, body = envelope(["config", "set", "language", "pt", "-f", "json"], capsys)
    assert code == 0
    assert body["data"] == {"key": "language", "value": "pt"}

    # the refusal arrives in the language just chosen -- the setting takes
    # effect on the very next command, including the one that rejects a bad
    # value for it
    code, body = envelope(["config", "set", "language", "klingon", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["code"] == "validation"
    assert body["error"]["message"] == 'Idioma "klingon" nao existe. Idiomas validos: en, pt.'
    code, body = envelope(["config", "get", "language", "-f", "json"], capsys)
    assert body["data"]["value"] == "pt"


# QA-CFG-009
def test_the_stored_language_changes_what_a_command_says(tmp_config_dir, capsys, monkeypatch):
    """The point of the whole catalogue, end to end: the same refusal, read
    by the same caller, in the language they chose."""
    monkeypatch.delenv("DBQM_LANG", raising=False)
    code, body = envelope(["connection", "add", "x", "--type", "h2", "--no-password", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["message"].startswith("Invalid database type: h2.")

    code, _ = envelope(["config", "set", "language", "pt", "-f", "json"], capsys)
    assert code == 0
    code, body = envelope(["connection", "add", "x", "--type", "h2", "--no-password", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["message"].startswith("Tipo de banco invalido: h2.")


# QA-CFG-010
def test_DBQM_LANG_overrides_the_stored_language(tmp_config_dir, capsys, monkeypatch):
    code, _ = envelope(["config", "set", "language", "pt", "-f", "json"], capsys)
    assert code == 0
    monkeypatch.setenv("DBQM_LANG", "en")
    code, body = envelope(["connection", "add", "x", "--type", "h2", "--no-password", "-f", "json"], capsys)
    assert code == 2
    assert body["error"]["message"].startswith("Invalid database type: h2.")
