"""Tests for settings model."""
from dbqm.models.settings import Settings, load_settings, save_settings


class TestSettings:
    def test_defaults(self):
        s = Settings()
        assert s.audit_log_enabled is False

    def test_round_trip(self):
        s = Settings(audit_log_enabled=True)
        s2 = Settings.from_dict(s.to_dict())
        assert s2.audit_log_enabled is True

    def test_save_and_load(self, tmp_config_dir):
        save_settings(Settings(audit_log_enabled=True))
        loaded = load_settings()
        assert loaded.audit_log_enabled is True

    def test_load_default_when_missing(self, tmp_config_dir):
        s = load_settings()
        assert s.audit_log_enabled is False

    def test_export_field_defaults(self):
        s = Settings()
        assert s.default_export_dir == ""
        assert s.export_dir_prompted is False
        assert s.create_export_subdirs is True

    def test_export_fields_round_trip(self):
        s = Settings(
            default_export_dir="/tmp/exports",
            export_dir_prompted=True,
            create_export_subdirs=False,
        )
        s2 = Settings.from_dict(s.to_dict())
        assert s2.default_export_dir == "/tmp/exports"
        assert s2.export_dir_prompted is True
        assert s2.create_export_subdirs is False

    def test_export_fields_save_and_load(self, tmp_config_dir):
        save_settings(Settings(
            default_export_dir=str(tmp_config_dir),
            export_dir_prompted=True,
            create_export_subdirs=False,
        ))
        loaded = load_settings()
        assert loaded.default_export_dir == str(tmp_config_dir)
        assert loaded.export_dir_prompted is True
        assert loaded.create_export_subdirs is False

    def test_load_missing_export_keys_uses_defaults(self, tmp_config_dir):
        """Settings written before the export fields existed must load without errors."""
        import json
        from dbqm.core.paths import SETTINGS_FILE
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # "github-light" e de proposito: e o nome do tema de antes da migracao
        # para design tokens. Este teste prova que um settings.json gravado
        # antes dela ainda carrega sem erro — nao "corrigir" para plano-claro.
        SETTINGS_FILE.write_text(
            json.dumps({"audit_log_enabled": True, "theme": "github-light"}),
            encoding="utf-8",
        )
        s = load_settings()
        assert s.audit_log_enabled is True
        assert s.theme == "github-light"  # passthrough cru; get_theme() e quem normaliza
        assert s.default_export_dir == ""
        assert s.export_dir_prompted is False
        assert s.create_export_subdirs is True

    def test_oracle_client_dir_defaults_to_empty(self):
        assert Settings().oracle_client_dir == ""

    def test_oracle_client_dir_round_trip(self):
        s2 = Settings.from_dict(Settings(oracle_client_dir="/opt/instantclient_19").to_dict())
        assert s2.oracle_client_dir == "/opt/instantclient_19"

    def test_oracle_client_dir_save_and_load(self, tmp_config_dir):
        save_settings(Settings(oracle_client_dir=str(tmp_config_dir)))
        assert load_settings().oracle_client_dir == str(tmp_config_dir)

    def test_load_missing_oracle_client_dir_uses_default(self, tmp_config_dir):
        """settings.json written before the field existed must still load."""
        import json
        from dbqm.core.paths import SETTINGS_FILE
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        # De proposito: settings.json legado, de antes da migracao para tokens.
        SETTINGS_FILE.write_text(json.dumps({"theme": "github-light"}), encoding="utf-8")
        assert load_settings().oracle_client_dir == ""
