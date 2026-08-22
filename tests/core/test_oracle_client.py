"""Oracle Instant Client resolution — dbqm settings must override ORACLE_HOME.

Users running an old PL/SQL Developer have a 32-bit Instant Client wired into
ORACLE_HOME. dbqm needs the 64-bit one, so the client directory is configured
in dbqm's own settings and the environment variable is only a last resort.
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

from dbqm.models.connection import Connection
from dbqm.core.db_manager import _find_oracle_client_dir

MACHINE_AMD64 = 0x8664
MACHINE_I386 = 0x014C


def _write_oci_dll(path, machine):
    """Write a minimal PE stub whose COFF header declares `machine`."""
    pe_offset = 0x80
    buf = bytearray(pe_offset + 8)
    buf[0:2] = b"MZ"
    buf[0x3C:0x40] = pe_offset.to_bytes(4, "little")
    buf[pe_offset:pe_offset + 4] = b"PE\x00\x00"
    buf[pe_offset + 4:pe_offset + 6] = machine.to_bytes(2, "little")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))


def _make_client(base, name, machine=MACHINE_AMD64, dll_subdir=""):
    """Create a fake Oracle client directory containing an oci.dll."""
    d = base / name
    d.mkdir(parents=True, exist_ok=True)
    dll = (d / dll_subdir / "oci.dll") if dll_subdir else (d / "oci.dll")
    _write_oci_dll(dll, machine)
    return d


def _configure(path):
    from dbqm.models.settings import load_settings, save_settings

    s = load_settings()
    s.oracle_client_dir = str(path)
    save_settings(s)


@pytest.fixture
def client_env(tmp_path, tmp_config_dir, monkeypatch):
    """Neutralize every client source so each test enables just the one it exercises."""
    empty = tmp_path / "no-clients"
    empty.mkdir()
    monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", empty)
    monkeypatch.setattr("dbqm.core.db_manager._PKG_CLIENTS_DIR", tmp_path / "absent")
    monkeypatch.setattr("dbqm.core.db_manager._scan_common_locations", lambda: None)
    monkeypatch.delenv("ORACLE_HOME", raising=False)
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr("platform.machine", lambda: "AMD64")
    return tmp_path


class TestOracleClientResolution:
    """The configured path wins, and a foreign ORACLE_HOME must never smuggle
    in a client of the wrong architecture."""

    def test_configured_dir_wins_over_clients_dir_and_oracle_home(self, client_env, monkeypatch):
        from dbqm.core.db_manager import resolve_oracle_client_dir

        chosen = _make_client(client_env, "chosen_x64")
        managed = client_env / "managed"
        _make_client(managed, "instantclient_19_x64")
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", managed)
        monkeypatch.setenv("ORACLE_HOME", str(_make_client(client_env, "env_home")))
        _configure(chosen)

        path, origin = resolve_oracle_client_dir()
        assert path == str(chosen)
        assert origin == "config"

    def test_configured_dir_that_does_not_exist_raises_instead_of_falling_back(
        self, client_env, monkeypatch
    ):
        from dbqm.core.db_manager import OracleClientConfigError, resolve_oracle_client_dir

        managed = client_env / "managed"
        _make_client(managed, "instantclient_19_x64")
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", managed)
        _configure(client_env / "gone")

        with pytest.raises(OracleClientConfigError) as exc:
            resolve_oracle_client_dir()
        assert "gone" in str(exc.value)

    def test_configured_dir_with_wrong_architecture_raises(self, client_env):
        from dbqm.core.db_manager import OracleClientConfigError, resolve_oracle_client_dir

        _configure(_make_client(client_env, "ic_x86", machine=MACHINE_I386))
        with pytest.raises(OracleClientConfigError) as exc:
            resolve_oracle_client_dir()
        assert "32" in str(exc.value)

    def test_falls_back_to_managed_clients_dir_when_not_configured(self, client_env, monkeypatch):
        from dbqm.core.db_manager import resolve_oracle_client_dir

        managed = client_env / "managed"
        _make_client(managed, "instantclient_19_x64")
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", managed)

        path, origin = resolve_oracle_client_dir()
        assert path.endswith("instantclient_19_x64")
        assert origin == "clients"

    def test_oracle_home_32bit_with_oci_dll_in_bin_is_rejected(self, client_env, monkeypatch):
        """A full Oracle Home keeps oci.dll under bin/; the old check only looked
        at the root, so a 32-bit home slipped through unvalidated."""
        from dbqm.core.db_manager import resolve_oracle_client_dir

        home = _make_client(client_env, "ora_home_32", machine=MACHINE_I386, dll_subdir="bin")
        monkeypatch.setenv("ORACLE_HOME", str(home))

        assert resolve_oracle_client_dir() == (None, "none")

    def test_oracle_home_64bit_with_oci_dll_in_bin_is_accepted(self, client_env, monkeypatch):
        from dbqm.core.db_manager import resolve_oracle_client_dir

        home = _make_client(client_env, "ora_home_64", machine=MACHINE_AMD64, dll_subdir="bin")
        monkeypatch.setenv("ORACLE_HOME", str(home))

        path, origin = resolve_oracle_client_dir()
        assert path == str(home)
        assert origin == "ORACLE_HOME"

    def test_oracle_home_without_any_oci_dll_is_rejected_on_windows(self, client_env, monkeypatch):
        from dbqm.core.db_manager import resolve_oracle_client_dir

        home = client_env / "not_a_client"
        home.mkdir()
        monkeypatch.setenv("ORACLE_HOME", str(home))

        assert resolve_oracle_client_dir() == (None, "none")

    def test_find_oracle_client_dir_still_returns_the_resolved_path(self, client_env, monkeypatch):
        managed = client_env / "managed"
        _make_client(managed, "instantclient_19_x64")
        monkeypatch.setattr("dbqm.core.db_manager.CLIENTS_DIR", managed)

        assert _find_oracle_client_dir().endswith("instantclient_19_x64")


class TestValidateOracleClientDir:
    """Validation the settings UI runs before persisting a user-typed path."""

    def test_accepts_matching_client(self, client_env):
        from dbqm.core.db_manager import validate_oracle_client_dir

        assert validate_oracle_client_dir(str(_make_client(client_env, "ic_x64"))) is None

    def test_rejects_missing_dir(self, client_env):
        from dbqm.core.db_manager import validate_oracle_client_dir

        assert "existe" in validate_oracle_client_dir(str(client_env / "nope"))

    def test_rejects_wrong_architecture(self, client_env):
        from dbqm.core.db_manager import validate_oracle_client_dir

        msg = validate_oracle_client_dir(
            str(_make_client(client_env, "ic_x86", machine=MACHINE_I386))
        )
        assert msg is not None and "32" in msg

    def test_rejects_dir_without_oci_dll_on_windows(self, client_env):
        from dbqm.core.db_manager import validate_oracle_client_dir

        d = client_env / "empty_dir"
        d.mkdir()
        assert "oci.dll" in validate_oracle_client_dir(str(d))


class TestThickModeErrorSurfacing:
    """A failed thick-mode init must not leave the user staring at a bare
    network error produced by the silent thin-mode fallback."""

    def _conn(self):
        return Connection(
            name="t", db_type="oracle", user="u", password="p",
            mode="direct", host="h", port=1521, service_name="s",
        )

    def _raise_from_connect(self, monkeypatch, thick_error, connect_error):
        import dbqm.core.db_manager as dm

        monkeypatch.setattr(dm, "decrypt", lambda _: "pw")
        monkeypatch.setattr(dm, "_thick_mode_initialized", True)
        monkeypatch.setattr(dm, "_thick_mode_error", thick_error)

        fake = MagicMock()
        fake.connect.side_effect = Exception(connect_error)
        fake.makedsn.return_value = "dsn"
        with patch.dict(sys.modules, {"oracledb": fake}):
            with pytest.raises(Exception) as exc:
                dm.get_oracle_connection(self._conn())
        return str(exc.value)

    def test_connection_error_reports_that_the_client_was_not_loaded(self, monkeypatch):
        msg = self._raise_from_connect(
            monkeypatch,
            thick_error="DPI-1047: Cannot locate a 64-bit Oracle Client",
            connect_error="DPY-6005: cannot connect to database",
        )
        assert "DPY-6005" in msg
        assert "Instant Client" in msg
        assert "DPI-1047" in msg

    def test_connection_error_untouched_when_client_loaded_fine(self, monkeypatch):
        msg = self._raise_from_connect(
            monkeypatch,
            thick_error=None,
            connect_error="ORA-01017: invalid credential",
        )
        assert "Instant Client" not in msg

    def test_guidance_points_to_dbqm_config_not_oracle_home(self, monkeypatch):
        msg = self._raise_from_connect(
            monkeypatch,
            thick_error="DPI-1047",
            connect_error="DPY-3015: password verifier type is not supported",
        )
        assert "ORACLE_HOME" not in msg
        assert "Config" in msg and "Oracle Instant Client" in msg


class TestConnectionMessageKeepsClientGuidance:
    """`test_connection` truncates errors to one line for compact display, which
    would drop the multi-line Instant Client guidance the user needs to act on."""

    def _conn(self):
        return Connection(
            name="t", db_type="oracle", user="u", password="p",
            mode="direct", host="h", port=1521, service_name="s",
        )

    def _test_connection_message(self, monkeypatch, thick_error, connect_error):
        import dbqm.core.db_manager as dm

        monkeypatch.setattr(dm, "decrypt", lambda _: "pw")
        monkeypatch.setattr(dm, "_thick_mode_initialized", True)
        monkeypatch.setattr(dm, "_thick_mode_error", thick_error)

        fake = MagicMock()
        fake.connect.side_effect = Exception(connect_error)
        fake.makedsn.return_value = "dsn"
        with patch.dict(sys.modules, {"oracledb": fake}):
            ok, msg = dm.test_connection(self._conn())
        assert ok is False
        return msg

    def test_keeps_the_instant_client_guidance(self, monkeypatch):
        msg = self._test_connection_message(
            monkeypatch,
            thick_error="DPI-1047: Cannot locate a 64-bit Oracle Client library",
            connect_error="DPY-6005: cannot connect to database",
        )
        assert "Config > Oracle Instant Client" in msg
        assert "DPI-1047" in msg

    def test_still_truncates_ordinary_errors_to_one_line(self, monkeypatch):
        msg = self._test_connection_message(
            monkeypatch,
            thick_error=None,
            connect_error="ORA-01017: invalid credential\nlinha extra que nao deve aparecer",
        )
        assert "linha extra" not in msg
