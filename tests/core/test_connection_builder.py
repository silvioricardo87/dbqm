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
        # "sqlite" was this test's example of an invalid type until 2.9.0
        # made it the fifth engine. H2 is Java; it will never be one here.
        errors = validate({"name": "prod", "db_type": "h2"})
        assert errors == [
            (
                "Tipo de banco invalido: h2. "
                "Use um de: oracle, sqlserver, postgresql, mysql, sqlite."
            )
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
    def test_default_ports_cover_every_networked_db_type(self):
        """SQLite is a file: it has no port, and giving it one to satisfy a
        set equality would be a lie the connection form then displays."""
        assert set(DEFAULT_PORTS) == set(DB_TYPES) - {"sqlite"}

    def test_default_hosts_only_where_localhost_makes_sense(self):
        assert DEFAULT_HOSTS == {"postgresql": "localhost", "mysql": "localhost"}

    def test_oracle_modes(self):
        assert ORACLE_MODES == ("direct", "tns")


def _existing(**kwargs) -> Connection:
    defaults = {
        "name": "prod", "db_type": "oracle", "user": "admin", "password": "ciphertext",
        "mode": "direct", "host": "old.example.com", "port": 1521, "service_name": "OLD",
        "created_at": "2020-01-01T00:00:00",
    }
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


from dbqm.core.connection_builder import upsert
from dbqm.models.connection import find_connection, load_connections, save_connections


class TestUpsert:
    def test_creates_when_the_name_is_new(self, tmp_config_dir):
        conn, created = upsert({"name": "nova", "db_type": "mysql", "host": "h"})
        assert created is True
        assert find_connection("nova").host == "h"

    def test_updates_in_place_when_the_name_exists(self, tmp_config_dir):
        upsert({"name": "nova", "db_type": "mysql", "host": "h",
                "password": "pw"})
        conn, created = upsert({"name": "nova", "db_type": "mysql",
                                "host": "outro"})
        assert created is False
        assert find_connection("nova").host == "outro"
        assert len(load_connections()) == 1, "an update must not append a copy"

    def test_an_update_keeps_the_stored_password(self, tmp_config_dir):
        from dbqm.core.crypto import decrypt

        upsert({"name": "nova", "db_type": "mysql", "password": "pw"})
        upsert({"name": "nova", "db_type": "mysql", "host": "outro"})
        assert decrypt(find_connection("nova").password) == "pw"

    def test_the_position_in_the_list_is_preserved(self, tmp_config_dir):
        upsert({"name": "a", "db_type": "mysql"})
        upsert({"name": "b", "db_type": "mysql"})
        upsert({"name": "a", "db_type": "mysql", "host": "novo"})
        assert [c.name for c in load_connections()] == ["a", "b"]


class TestReadOnlyInBuild:
    """Keyed on presence, like `password`: an absent key means keep what is
    stored, so `connection update --host x` does not silently unlock a
    protected connection."""

    def test_it_is_set_from_the_values(self):
        from dbqm.core.connection_builder import build

        c = build({"name": "c", "db_type": "mysql", "host": "h", "user": "u",
                   "read_only": True})
        assert c.read_only is True

    def test_it_defaults_to_false_when_absent_and_new(self):
        from dbqm.core.connection_builder import build

        c = build({"name": "c", "db_type": "mysql", "host": "h", "user": "u"})
        assert c.read_only is False

    def test_an_absent_key_keeps_what_is_stored(self):
        """The rule that matters: updating any other field must not unlock."""
        from dbqm.core.connection_builder import build
        from dbqm.models.connection import Connection

        existente = Connection(name="c", db_type="mysql", user="u",
                               password="", host="antigo", read_only=True)
        c = build({"name": "c", "db_type": "mysql", "host": "novo",
                   "user": "u"}, existing=existente)
        assert c.read_only is True, "an unrelated update must not unlock"

    def test_a_present_false_unlocks(self):
        from dbqm.core.connection_builder import build
        from dbqm.models.connection import Connection

        existente = Connection(name="c", db_type="mysql", user="u",
                               password="", read_only=True)
        c = build({"name": "c", "db_type": "mysql", "host": "h", "user": "u",
                   "read_only": False}, existing=existente)
        assert c.read_only is False


class TestSqlite:
    """One file is the whole configuration."""

    def test_sqlite_is_a_valid_type_and_needs_only_a_database(self, tmp_config_dir):
        assert validate({"name": "l", "db_type": "sqlite", "database": "a.db"}) == []

    def test_sqlite_without_a_database_is_refused(self, tmp_config_dir):
        erros = validate({"name": "l", "db_type": "sqlite"})
        assert any("arquivo" in e.lower() for e in erros)

    def test_sqlite_refuses_a_host_it_cannot_use(self, tmp_config_dir):
        """A user who typed a host for a SQLite file has misunderstood
        something; saying so beats ignoring it."""
        erros = validate({"name": "l", "db_type": "sqlite", "database": "a.db", "host": "srv"})
        assert any("host" in e.lower() for e in erros)

    def test_build_stores_only_the_file(self, tmp_config_dir):
        """No empty host lingering in the JSON to read like a real one."""
        conn = build({"name": "l", "db_type": "sqlite", "database": "a.db"})
        assert conn.database == "a.db"
        assert conn.host is None
        assert conn.port is None
        assert "host" not in conn.to_dict()
