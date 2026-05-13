"""Tests for database connection manager — dispatcher and test_connection."""
import os
import sys
from unittest.mock import patch, MagicMock
import pytest

from dbqm.models.connection import Connection
from dbqm.core.db_manager import (
    get_connection,
    _ensure_utf8_nls_lang,
    _find_oracle_client_dir,
    _missing_driver_message,
    get_oracle_connection,
    get_postgresql_connection,
    get_sqlserver_connection,
    get_mysql_connection,
)
from dbqm.core.db_manager import test_connection as db_test_connection


class TestGetConnection:
    def test_oracle_dispatch(self):
        conn = Connection(name="t", db_type="oracle", user="u", password="p", mode="direct", host="h", port=1521, service_name="s")
        with patch("dbqm.core.db_manager.get_oracle_connection") as mock:
            mock.return_value = MagicMock()
            get_connection(conn)
            mock.assert_called_once_with(conn)

    def test_sqlserver_dispatch(self):
        conn = Connection(name="t", db_type="sqlserver", user="u", password="p", host="h")
        with patch("dbqm.core.db_manager.get_sqlserver_connection") as mock:
            mock.return_value = MagicMock()
            get_connection(conn)
            mock.assert_called_once_with(conn)

    def test_postgresql_dispatch(self):
        conn = Connection(name="t", db_type="postgresql", user="u", password="p", host="h")
        with patch("dbqm.core.db_manager.get_postgresql_connection") as mock:
            mock.return_value = MagicMock()
            get_connection(conn)
            mock.assert_called_once_with(conn)

    def test_mysql_dispatch(self):
        conn = Connection(name="t", db_type="mysql", user="u", password="p", host="h")
        with patch("dbqm.core.db_manager.get_mysql_connection") as mock:
            mock.return_value = MagicMock()
            get_connection(conn)
            mock.assert_called_once_with(conn)

    def test_unknown_raises(self):
        conn = Connection(name="t", db_type="unknown", user="u", password="p")
        with pytest.raises(ValueError, match="desconhecido"):
            get_connection(conn)


class TestTestConnection:
    def _mock_conn(self, db_type):
        return Connection(name="t", db_type=db_type, user="u", password="p", host="h")

    def test_success(self):
        mock_db = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("PostgreSQL 16.0",)
        mock_db.cursor.return_value = mock_cursor

        conn = self._mock_conn("postgresql")
        with patch("dbqm.core.db_manager.get_connection", return_value=mock_db):
            success, msg = db_test_connection(conn)

        assert success is True
        assert "OK" in msg
        assert "PostgreSQL" in msg

    def test_failure(self):
        conn = self._mock_conn("oracle")
        with patch("dbqm.core.db_manager.get_connection", side_effect=Exception("Connection refused")):
            success, msg = db_test_connection(conn)

        assert success is False
        assert "Erro" in msg


class TestEnsureUtf8NlsLang:
    """`_ensure_utf8_nls_lang` forces NLS_LANG to a UTF-8 charset on init.

    Required so the Oracle thick client returns server messages in UTF-8;
    otherwise on Windows, accented Portuguese error text gets mis-decoded
    (e.g. `s�mbolo` instead of `símbolo`).
    """

    def test_sets_nls_lang_when_unset(self, monkeypatch):
        monkeypatch.delenv("NLS_LANG", raising=False)
        _ensure_utf8_nls_lang()
        assert os.environ["NLS_LANG"] == ".AL32UTF8"

    def test_overrides_non_utf8_charset(self, monkeypatch):
        monkeypatch.setenv("NLS_LANG", "BRAZILIAN PORTUGUESE_BRAZIL.WE8MSWIN1252")
        _ensure_utf8_nls_lang()
        assert os.environ["NLS_LANG"] == "BRAZILIAN PORTUGUESE_BRAZIL.AL32UTF8"

    def test_preserves_existing_utf8(self, monkeypatch):
        monkeypatch.setenv("NLS_LANG", "AMERICAN_AMERICA.AL32UTF8")
        _ensure_utf8_nls_lang()
        assert os.environ["NLS_LANG"] == "AMERICAN_AMERICA.AL32UTF8"

    def test_preserves_existing_utf8_lowercase(self, monkeypatch):
        monkeypatch.setenv("NLS_LANG", "american_america.utf8")
        _ensure_utf8_nls_lang()
        # Already UTF8 → leave untouched
        assert os.environ["NLS_LANG"] == "american_america.utf8"

    def test_charset_only_value_overridden(self, monkeypatch):
        monkeypatch.setenv("NLS_LANG", "WE8MSWIN1252")
        _ensure_utf8_nls_lang()
        # No `.` means no language/territory prefix to preserve.
        assert os.environ["NLS_LANG"] == ".AL32UTF8"


class TestMissingDriverMessage:
    """Hint message must name the database, the package, and the platform."""

    def test_includes_db_label_and_package(self):
        msg = _missing_driver_message("PostgreSQL", "psycopg[binary]")
        assert "PostgreSQL" in msg
        assert "psycopg[binary]" in msg
        assert "pip install" in msg

    def test_mentions_windows_arm_caveat(self):
        msg = _missing_driver_message("SQL Server", "pymssql")
        assert "Windows ARM" in msg


class TestFindOracleClientDir:
    """Auto-detection of Oracle Instant Client must match the running platform.

    Older installs only had `instantclient_19_x64`/`_x86` (Windows-only naming);
    macOS/Linux ARM builds introduce `arm64`/`aarch64` tags. The detector must
    not return a Windows directory when running on macOS/Linux and vice versa.
    """

    def _make_dirs(self, tmp_path, names):
        for n in names:
            (tmp_path / n).mkdir()
        return tmp_path

    def test_macos_arm_prefers_arm64_dir(self, tmp_path, monkeypatch):
        base = self._make_dirs(tmp_path, ["instantclient_19_x64", "instantclient_23_arm64"])
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", base)
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        result = _find_oracle_client_dir()
        assert result is not None
        assert result.endswith("instantclient_23_arm64")

    def test_macos_arm_skips_windows_only_dirs(self, tmp_path, monkeypatch):
        base = self._make_dirs(tmp_path, ["instantclient_19_x64", "instantclient_19_x86"])
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", base)
        monkeypatch.setenv("ORACLE_HOME", "")
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        # Force the package-local fallback to also miss.
        monkeypatch.setattr("pathlib.Path.exists", lambda self: self == base)
        result = _find_oracle_client_dir()
        assert result is None

    def test_windows_picks_x64_when_present(self, tmp_path, monkeypatch):
        base = self._make_dirs(tmp_path, ["instantclient_19_x64", "instantclient_23_arm64"])
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", base)
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr("platform.machine", lambda: "AMD64")
        result = _find_oracle_client_dir()
        assert result is not None
        assert result.endswith("instantclient_19_x64")


class TestDriversRaiseHelpfulErrorWhenAbsent:
    """When the driver wheel was not installed (e.g. win-arm64), the
    connect helpers must raise a RuntimeError with a hint instead of
    bubbling up the bare ImportError."""

    def _conn(self, db_type):
        return Connection(name="t", db_type=db_type, user="u", password="p", host="h")

    def test_oracle_missing_driver(self):
        with patch.dict(sys.modules, {"oracledb": None}):
            with pytest.raises(RuntimeError, match="Oracle"):
                get_oracle_connection(self._conn("oracle"))

    def test_postgresql_missing_driver(self):
        with patch.dict(sys.modules, {"psycopg": None}):
            with pytest.raises(RuntimeError, match="PostgreSQL"):
                get_postgresql_connection(self._conn("postgresql"))

    def test_sqlserver_missing_driver(self):
        with patch.dict(sys.modules, {"pymssql": None}):
            with pytest.raises(RuntimeError, match="SQL Server"):
                get_sqlserver_connection(self._conn("sqlserver"))

    def test_mysql_missing_driver(self):
        with patch.dict(sys.modules, {"pymysql": None}):
            with pytest.raises(RuntimeError, match="MySQL"):
                get_mysql_connection(self._conn("mysql"))
