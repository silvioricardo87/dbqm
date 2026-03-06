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
