"""Tests for audit logging."""
import json
from dbqm.core.audit import log_execution
from dbqm.models.settings import Settings, save_settings


class TestAuditLog:
    def test_disabled_by_default(self, tmp_config_dir):
        log_execution("query", "test")
        audit_file = tmp_config_dir / "config" / "audit.log"
        assert not audit_file.exists()

    def test_enabled_writes_log(self, tmp_config_dir):
        save_settings(Settings(audit_log_enabled=True))
        log_execution("query", "test_query", connection="c1", row_count=5, success=True)
        audit_file = tmp_config_dir / "config" / "audit.log"
        assert audit_file.exists()
        line = audit_file.read_text().strip()
        entry = json.loads(line)
        assert entry["action"] == "query"
        assert entry["name"] == "test_query"
        assert entry["row_count"] == 5

    def test_multiple_entries_appended(self, tmp_config_dir):
        save_settings(Settings(audit_log_enabled=True))
        log_execution("query", "q1")
        log_execution("query", "q2")
        audit_file = tmp_config_dir / "config" / "audit.log"
        lines = audit_file.read_text().strip().split("\n")
        assert len(lines) == 2

    def test_error_truncated(self, tmp_config_dir):
        save_settings(Settings(audit_log_enabled=True))
        log_execution("query", "q1", error="x" * 500)
        audit_file = tmp_config_dir / "config" / "audit.log"
        entry = json.loads(audit_file.read_text().strip())
        assert len(entry["error"]) <= 200
