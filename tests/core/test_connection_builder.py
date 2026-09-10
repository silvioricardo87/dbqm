"""Tests for the UI-agnostic connection rules."""
from __future__ import annotations

import pytest

from dbqm.core.connection_builder import (
    DEFAULT_HOSTS,
    DEFAULT_PORTS,
    DB_TYPES,
    ORACLE_MODES,
    build,
    validate,
)
from dbqm.core.crypto import decrypt
from dbqm.models.connection import Connection


class TestValidate:
    def test_a_complete_oracle_value_set_is_valid(self):
        values = {"name": "prod", "db_type": "oracle", "mode": "direct"}
        assert validate(values) == []

    def test_missing_name_is_reported(self):
        assert "Nome obrigatorio." in validate({"db_type": "mysql"})

    def test_whitespace_only_name_is_reported(self):
        assert "Nome obrigatorio." in validate({"name": "   ", "db_type": "mysql"})

    def test_missing_db_type_is_reported(self):
        assert "Selecione o tipo de banco." in validate({"name": "prod"})

    def test_unknown_db_type_lists_the_valid_ones(self):
        errors = validate({"name": "prod", "db_type": "sqlite"})
        assert errors == [
            "Tipo de banco invalido: sqlite. "
            "Use um de: oracle, sqlserver, postgresql, mysql."
        ]

    def test_unknown_oracle_mode_lists_the_valid_ones(self):
        errors = validate({"name": "prod", "db_type": "oracle", "mode": "sid"})
        assert errors == ["Modo Oracle invalido: sid. Use um de: direct, tns."]

    def test_mode_is_ignored_for_non_oracle(self):
        assert validate({"name": "prod", "db_type": "mysql", "mode": "sid"}) == []

    def test_blank_host_user_and_password_are_accepted(self):
        """The TUI saves those blank today; the CLI must not be stricter."""
        values = {"name": "prod", "db_type": "mysql", "host": "", "user": "",
                  "password": ""}
        assert validate(values) == []

    def test_several_problems_are_all_reported(self):
        errors = validate({})
        assert "Nome obrigatorio." in errors
        assert "Selecione o tipo de banco." in errors


class TestConstants:
    def test_default_ports_cover_every_db_type(self):
        assert set(DEFAULT_PORTS) == set(DB_TYPES)

    def test_default_hosts_only_where_localhost_makes_sense(self):
        assert DEFAULT_HOSTS == {"postgresql": "localhost", "mysql": "localhost"}

    def test_oracle_modes(self):
        assert ORACLE_MODES == ("direct", "tns")


def _existing(**kwargs) -> Connection:
    defaults = dict(
        name="prod", db_type="oracle", user="admin", password="ciphertext",
        mode="direct", host="old.example.com", port=1521, service_name="OLD",
        created_at="2020-01-01T00:00:00",
    )
    defaults.update(kwargs)
    return Connection(**defaults)


class TestBuildDefaults:
    def test_blank_port_falls_back_to_the_engine_default(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "postgresql", "host": "h"})
        assert conn.port == 5432

    def test_blank_host_falls_back_for_postgresql(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "postgresql"})
        assert conn.host == "localhost"

    def test_blank_host_stays_blank_for_oracle(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "oracle", "mode": "direct"})
        assert conn.host == ""

    def test_unparsable_port_falls_back_to_the_engine_default(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql", "port": "abc"})
        assert conn.port == 3306

    def test_given_port_wins(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql", "port": "3307"})
        assert conn.port == 3307

    def test_oracle_defaults_to_direct_mode(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "oracle"})
        assert conn.mode == "direct"


class TestBuildClearsIrrelevantFields:
    def test_oracle_tns_drops_host_port_and_service(self, tmp_config_dir):
        conn = build({
            "name": "p", "db_type": "oracle", "mode": "tns",
            "tns_path": "C:/tns", "tns_name": "ORCL",
            "host": "ignored", "port": "1521", "service_name": "ignored",
        })
        assert conn.tns_path == "C:/tns" and conn.tns_name == "ORCL"
        assert conn.host is None and conn.port is None
        assert conn.service_name is None

    def test_oracle_direct_drops_the_tns_fields(self, tmp_config_dir):
        conn = build({
            "name": "p", "db_type": "oracle", "mode": "direct",
            "host": "h", "service_name": "SVC",
            "tns_path": "ignored", "tns_name": "ignored",
        })
        assert conn.tns_path is None and conn.tns_name is None

    def test_non_oracle_drops_every_oracle_only_field(self, tmp_config_dir):
        conn = build({
            "name": "p", "db_type": "mysql", "host": "h", "database": "db",
            "mode": "tns", "service_name": "SVC", "tns_name": "ORCL",
        })
        assert conn.mode is None
        assert conn.service_name is None
        assert conn.tns_name is None and conn.tns_path is None
        assert conn.database == "db"

    def test_switching_an_existing_connection_to_tns_clears_host(self, tmp_config_dir):
        existing = _existing()
        conn = build(
            {"name": "prod", "db_type": "oracle", "mode": "tns",
             "tns_path": "C:/tns", "tns_name": "ORCL"},
            existing,
        )
        assert conn.host is None and conn.service_name is None


class TestBuildPassword:
    def test_a_given_password_is_encrypted(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql", "password": "s3cret"})
        assert conn.password != "s3cret"
        assert decrypt(conn.password) == "s3cret"

    def test_an_absent_password_key_keeps_the_existing_one(self, tmp_config_dir):
        existing = _existing(password="stored-ciphertext")
        conn = build({"name": "prod", "db_type": "oracle"}, existing)
        assert conn.password == "stored-ciphertext"

    def test_an_absent_password_key_with_no_existing_is_blank(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql"})
        assert conn.password == ""

    def test_an_empty_password_key_clears_the_existing_one(self, tmp_config_dir):
        existing = _existing(password="stored-ciphertext")
        conn = build({"name": "prod", "db_type": "oracle", "password": ""}, existing)
        assert conn.password == ""

    def test_surrounding_whitespace_in_the_password_is_preserved(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql", "password": " pw "})
        assert decrypt(conn.password) == " pw "


class TestBuildIdentity:
    def test_created_at_survives_an_update(self, tmp_config_dir):
        existing = _existing(created_at="2020-01-01T00:00:00")
        conn = build({"name": "prod", "db_type": "oracle"}, existing)
        assert conn.created_at == "2020-01-01T00:00:00"

    def test_a_new_connection_gets_its_own_created_at(self, tmp_config_dir):
        conn = build({"name": "p", "db_type": "mysql"})
        assert conn.created_at

    def test_existing_is_not_mutated(self, tmp_config_dir):
        existing = _existing(host="old.example.com")
        build({"name": "prod", "db_type": "oracle", "host": "new.example.com"}, existing)
        assert existing.host == "old.example.com"

    def test_name_and_description_are_trimmed(self, tmp_config_dir):
        conn = build({"name": "  p  ", "db_type": "mysql", "description": "  nota  "})
        assert conn.name == "p"
        assert conn.description == "nota"
