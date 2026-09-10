"""Tests for the UI-agnostic connection rules."""
from __future__ import annotations

from dbqm.core.connection_builder import (
    DEFAULT_HOSTS,
    DEFAULT_PORTS,
    DB_TYPES,
    ORACLE_MODES,
    validate,
)


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
