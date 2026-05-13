"""Tests for the Oracle Instant Client installer module."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from dbqm.core import oracle_client_installer as oci


class TestDetectHostPlatform:
    """The settings UI uses this to filter which downloads to show — getting
    it wrong means users see incompatible packages."""

    def test_macos_arm(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setattr("platform.machine", lambda: "arm64")
        assert oci.detect_host_platform() == ("darwin", "arm64")

    def test_macos_intel(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        monkeypatch.setattr("platform.machine", lambda: "x86_64")
        assert oci.detect_host_platform() == ("darwin", "x86_64")

    def test_windows_x64(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "win32")
        monkeypatch.setattr("platform.machine", lambda: "AMD64")
        # struct.calcsize("P") returns 8 on 64-bit Python (which test runs on)
        assert oci.detect_host_platform() == ("win32", "x64")

    def test_linux_aarch64(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("platform.machine", lambda: "aarch64")
        assert oci.detect_host_platform() == ("linux", "aarch64")


class TestCatalog:
    """Every supported platform must expose at least one downloadable package
    and the URLs must point at Oracle's CDN."""

    def test_every_listed_platform_has_at_least_one_package(self):
        for host in oci.iter_supported_platforms():
            pkgs = oci.available_clients(host)
            assert pkgs, f"No packages for {host}"

    def test_urls_target_oracle_cdn(self):
        for host in oci.iter_supported_platforms():
            for pkg in oci.available_clients(host):
                assert pkg.url.startswith("https://download.oracle.com/"), pkg.url

    def test_archive_types_are_zip_or_dmg(self):
        for host in oci.iter_supported_platforms():
            for pkg in oci.available_clients(host):
                assert pkg.archive_type in ("zip", "dmg")

    def test_unknown_platform_returns_empty(self):
        assert oci.available_clients(("plan9", "riscv")) == ()


class TestInstallDirname:
    def test_uses_major_version_and_arch(self):
        pkg = oci.ClientPackage(
            version="23.26.1.0.0", url="https://download.oracle.com/x.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        )
        assert pkg.install_dirname == "instantclient_23_x64"

    def test_latest_label_falls_back(self):
        pkg = oci.ClientPackage(
            version="latest", url="https://download.oracle.com/x.zip",
            archive_type="zip", os_key="linux", arch_key="x86_64",
        )
        assert pkg.install_dirname == "instantclient_latest_x86_64"


class TestListInstalledClients:
    def test_empty_when_dir_missing(self, tmp_path):
        assert oci.list_installed_clients(tmp_path / "nope") == []

    def test_lists_instantclient_subdirs_with_version(self, tmp_path):
        a = tmp_path / "instantclient_23_x64"
        a.mkdir()
        (a / "BASIC_README").write_text(
            "Basic Package Information\nClient Shared Library 64-bit - 23.26.1.0.0\n",
            encoding="utf-8",
        )
        b = tmp_path / "instantclient_19_arm64"
        b.mkdir()  # no README → version stays None
        # Non-instantclient dirs ignored
        (tmp_path / "tns").mkdir()

        out = oci.list_installed_clients(tmp_path)
        names = [c.path.name for c in out]
        versions = {c.path.name: c.version for c in out}
        assert names == ["instantclient_19_arm64", "instantclient_23_x64"]
        assert versions["instantclient_23_x64"] == "23.26.1.0.0"
        assert versions["instantclient_19_arm64"] is None


class TestRemoveClient:
    """Path-traversal guard — only directories under CLIENTS_DIR may be removed."""

    def test_removes_existing_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path)
        target = tmp_path / "instantclient_23_x64"
        target.mkdir()
        (target / "oci.dll").write_text("stub")
        oci.remove_client(target)
        assert not target.exists()

    def test_rejects_outside_clients_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "dbqm.core.oracle_client_installer.CLIENTS_DIR", tmp_path / "managed",
        )
        (tmp_path / "managed").mkdir()
        outsider = tmp_path / "stranger"
        outsider.mkdir()
        with pytest.raises(ValueError, match="not under"):
            oci.remove_client(outsider)
        assert outsider.exists()


class TestInstallClient:
    """install_client downloads + extracts. We mock the network with an
    in-memory ZIP so the test is hermetic."""

    def _make_fake_zip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("instantclient_23_0/oci.dll", b"\x00\x01")
            zf.writestr(
                "instantclient_23_0/BASIC_README",
                "Client Shared Library 64-bit - 23.26.1.0.0\n",
            )
        return buf.getvalue()

    def test_zip_install_flattens_payload(self, tmp_path, monkeypatch):
        zip_bytes = self._make_fake_zip()

        def fake_download(url, dest_path, progress):
            Path(dest_path).write_bytes(zip_bytes)
            if progress is not None:
                progress(len(zip_bytes), len(zip_bytes))

        monkeypatch.setattr(oci, "_download", fake_download)
        pkg = oci.ClientPackage(
            version="23.26.1.0.0", url="https://download.oracle.com/x.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        )
        seen: list[int] = []
        result = oci.install_client(pkg, base_dir=tmp_path, progress=lambda d, t: seen.append(d))

        assert result == tmp_path / "instantclient_23_x64"
        assert (result / "oci.dll").exists()
        assert (result / "BASIC_README").read_text().startswith("Client Shared Library")
        assert seen, "progress callback was never invoked"

    def test_refuses_overwriting_non_empty_dir(self, tmp_path, monkeypatch):
        pkg = oci.ClientPackage(
            version="23.26.1.0.0", url="https://download.oracle.com/x.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        )
        existing = tmp_path / "instantclient_23_x64"
        existing.mkdir()
        (existing / "oci.dll").write_text("old")
        with patch.object(oci, "_download"):
            with pytest.raises(FileExistsError):
                oci.install_client(pkg, base_dir=tmp_path)
