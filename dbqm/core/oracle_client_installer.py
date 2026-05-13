"""Download, extract, and manage Oracle Instant Client installations.

The UI exposes this via a Settings screen so users without a compatible
client can grab one for the running OS/architecture without leaving dbqm.

Installs target `CLIENTS_DIR` (~/.dbqm/clients/) — picked up automatically
by `_find_oracle_client_dir` in `core.db_manager`.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from dbqm.core.paths import CLIENTS_DIR


HostKey = tuple[str, str]  # (os_key, arch_key) — e.g. ("darwin", "arm64")


@dataclass(frozen=True)
class ClientPackage:
    """One downloadable Oracle Instant Client Basic package."""
    version: str           # e.g. "23.26.1.0.0" or "latest"
    url: str
    archive_type: str      # "zip" | "dmg"
    os_key: str            # "darwin" | "win32" | "linux"
    arch_key: str          # "arm64" | "x86_64" | "x64" | "x86" | "aarch64"

    @property
    def display_label(self) -> str:
        return f"{self.version} ({self.os_key}/{self.arch_key})"

    @property
    def install_dirname(self) -> str:
        """Target subdirectory name under CLIENTS_DIR.

        Uses major version + arch tag so `_find_oracle_client_dir` can pick
        the right one per platform.
        """
        major = self.version.split(".")[0] if self.version[0].isdigit() else "latest"
        return f"instantclient_{major}_{self.arch_key}"


@dataclass(frozen=True)
class InstalledClient:
    """An Oracle Instant Client installation discovered under CLIENTS_DIR."""
    path: Path
    version: str | None     # parsed from BASIC_README when available


# Curated catalog of known-good Oracle Instant Client Basic packages.
# Versioned URLs are pinned; the "latest" URLs Oracle serves for some
# platforms are kept as a fallback so we never leave a platform empty.
_CATALOG: dict[HostKey, tuple[ClientPackage, ...]] = {
    ("darwin", "arm64"): (
        ClientPackage(
            version="23.26.1.0.0",
            url="https://download.oracle.com/otn_software/mac/instantclient/2326100/instantclient-basic-macos.arm64-23.26.1.0.0.dmg",
            archive_type="dmg", os_key="darwin", arch_key="arm64",
        ),
    ),
    ("darwin", "x86_64"): (
        ClientPackage(
            version="latest",
            url="https://download.oracle.com/otn_software/mac/instantclient/instantclient-basic-macos.dmg",
            archive_type="dmg", os_key="darwin", arch_key="x86_64",
        ),
    ),
    ("win32", "x64"): (
        ClientPackage(
            version="23.26.1.0.0",
            url="https://download.oracle.com/otn_software/nt/instantclient/2326100/instantclient-basic-windows.x64-23.26.1.0.0.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        ),
        ClientPackage(
            version="21.20.0.0.0",
            url="https://download.oracle.com/otn_software/nt/instantclient/2120000/instantclient-basic-windows.x64-21.20.0.0.0dbru.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        ),
        ClientPackage(
            version="19.30.0.0.0",
            url="https://download.oracle.com/otn_software/nt/instantclient/1930000/instantclient-basic-windows.x64-19.30.0.0.0dbru.zip",
            archive_type="zip", os_key="win32", arch_key="x64",
        ),
    ),
    ("win32", "x86"): (
        ClientPackage(
            version="latest",
            url="https://download.oracle.com/otn_software/nt/instantclient/instantclient-basic-nt.zip",
            archive_type="zip", os_key="win32", arch_key="x86",
        ),
    ),
    ("linux", "x86_64"): (
        ClientPackage(
            version="latest",
            url="https://download.oracle.com/otn_software/linux/instantclient/instantclient-basic-linuxx64.zip",
            archive_type="zip", os_key="linux", arch_key="x86_64",
        ),
    ),
    ("linux", "aarch64"): (
        ClientPackage(
            version="23.26.1.0.0",
            url="https://download.oracle.com/otn_software/linux/instantclient/2326100/instantclient-basic-linux.arm64-23.26.1.0.0.zip",
            archive_type="zip", os_key="linux", arch_key="aarch64",
        ),
        ClientPackage(
            version="19.30.0.0.0",
            url="https://download.oracle.com/otn_software/linux/instantclient/1930000/instantclient-basic-linux.arm64-19.30.0.0.0dbru.zip",
            archive_type="zip", os_key="linux", arch_key="aarch64",
        ),
    ),
}


_PLATFORM_LABELS: dict[HostKey, str] = {
    ("darwin", "arm64"): "macOS (Apple Silicon — ARM64)",
    ("darwin", "x86_64"): "macOS (Intel — x86_64)",
    ("win32", "x64"): "Windows (x64)",
    ("win32", "x86"): "Windows (x86 — 32 bits)",
    ("linux", "x86_64"): "Linux (x86_64)",
    ("linux", "aarch64"): "Linux (ARM64 — aarch64)",
}


def detect_host_platform() -> HostKey:
    """Identify the running OS/arch as a (os_key, arch_key) tuple.

    Falls back to a reasonable default ("linux", "x86_64") if the host
    is unrecognized — the catalog lookup will simply return no packages.
    """
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        arch = "arm64" if machine in ("arm64", "aarch64") else "x86_64"
        return ("darwin", arch)
    if sys.platform == "win32":
        # On Windows the running Python's bitness determines which
        # client binary it can load — not the host CPU.
        import struct
        is_64 = struct.calcsize("P") * 8 == 64
        return ("win32", "x64" if is_64 else "x86")
    if sys.platform.startswith("linux"):
        arch = "aarch64" if machine in ("aarch64", "arm64") else "x86_64"
        return ("linux", arch)
    return ("linux", "x86_64")


def host_platform_label(host: HostKey | None = None) -> str:
    h = host or detect_host_platform()
    return _PLATFORM_LABELS.get(h, f"{h[0]}/{h[1]}")


def available_clients(host: HostKey | None = None) -> tuple[ClientPackage, ...]:
    """Catalog entries downloadable for the current (or given) platform."""
    return _CATALOG.get(host or detect_host_platform(), ())


def list_installed_clients(base_dir: Path | None = None) -> list[InstalledClient]:
    """Scan CLIENTS_DIR for existing instantclient_* installations."""
    base = base_dir or CLIENTS_DIR
    if not base.exists():
        return []
    out: list[InstalledClient] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name):
        if entry.is_dir() and "instantclient" in entry.name.lower():
            out.append(InstalledClient(path=entry, version=_read_client_version(entry)))
    return out


def _read_client_version(client_dir: Path) -> str | None:
    """Parse the version from BASIC_README's `Client Shared Library` line."""
    readme = client_dir / "BASIC_README"
    if not readme.exists():
        return None
    try:
        for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
            if "Client Shared Library" in line:
                # "Client Shared Library 64-bit - 23.26.1.0.0"
                parts = line.rsplit("-", 1)
                if len(parts) == 2:
                    return parts[1].strip()
    except OSError:
        return None
    return None


ProgressCallback = Callable[[int, int | None], None]  # (bytes_so_far, total_bytes_or_None)


def install_client(
    pkg: ClientPackage,
    base_dir: Path | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    """Download `pkg` and extract it into `base_dir / pkg.install_dirname`.

    Raises:
        FileExistsError: target install directory is non-empty (caller must
            remove it first so we don't silently mix two installs).
        RuntimeError: archive type unsupported on this host or extraction failed.
    """
    base = base_dir or CLIENTS_DIR
    base.mkdir(parents=True, exist_ok=True)
    dest = base / pkg.install_dirname
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"Directory already exists with content: {dest}")
    dest.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dbqm-oic-") as tmp:
        suffix = ".dmg" if pkg.archive_type == "dmg" else ".zip"
        archive_path = Path(tmp) / f"client{suffix}"
        _download(pkg.url, archive_path, progress)
        if pkg.archive_type == "zip":
            _extract_zip(archive_path, dest)
        elif pkg.archive_type == "dmg":
            _extract_dmg(archive_path, dest)
        else:
            raise RuntimeError(f"Unsupported archive type: {pkg.archive_type}")
    return dest


def remove_client(client_dir: Path) -> None:
    """Delete an installed client directory (must live under CLIENTS_DIR)."""
    base = CLIENTS_DIR.resolve()
    target = client_dir.resolve()
    if not str(target).startswith(str(base)):
        raise ValueError(f"Refusing to remove {target}: not under {base}")
    shutil.rmtree(target)


def _download(url: str, dest: Path, progress: ProgressCallback | None) -> None:
    """Stream `url` to `dest`, calling `progress(bytes_so_far, total)` periodically."""
    req = urllib.request.Request(url, headers={"User-Agent": "dbqm-client-installer"})
    with urllib.request.urlopen(req) as resp:
        total = resp.length  # may be None
        chunk = 1 << 16
        done = 0
        with open(dest, "wb") as out:
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                done += len(buf)
                if progress is not None:
                    progress(done, total)


def _extract_zip(archive: Path, dest: Path) -> None:
    """Extract a Windows/Linux Instant Client ZIP, flattening the inner instantclient_* dir."""
    with zipfile.ZipFile(archive) as zf:
        with tempfile.TemporaryDirectory(prefix="dbqm-oic-x-") as tmp:
            tmp_path = Path(tmp)
            zf.extractall(tmp_path)
            _flatten_into(_pick_payload_dir(tmp_path), dest)


def _extract_dmg(archive: Path, dest: Path) -> None:
    """Mount a macOS DMG via hdiutil and copy contents (ditto preserves symlinks)."""
    if sys.platform != "darwin":
        raise RuntimeError("DMG archives can only be extracted on macOS")
    with tempfile.TemporaryDirectory(prefix="dbqm-oic-mnt-") as mnt_root:
        mnt = Path(mnt_root) / "oic"
        subprocess.run(
            ["hdiutil", "attach", str(archive), "-nobrowse", "-quiet",
             "-mountpoint", str(mnt)],
            check=True,
        )
        try:
            subprocess.run(["ditto", str(mnt) + "/", str(dest) + "/"], check=True)
        finally:
            subprocess.run(["hdiutil", "detach", str(mnt), "-quiet"], check=False)


def _pick_payload_dir(extracted_root: Path) -> Path:
    """Return the `instantclient_*` subdirectory inside an extracted archive.

    Oracle's zips usually nest content under `instantclient_<major>_<minor>/`.
    Fall back to the root if no such directory exists (defensive).
    """
    for entry in extracted_root.iterdir():
        if entry.is_dir() and entry.name.lower().startswith("instantclient"):
            return entry
    return extracted_root


def _flatten_into(src: Path, dest: Path) -> None:
    """Move all immediate children of `src` into `dest`."""
    for entry in src.iterdir():
        target = dest / entry.name
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        shutil.move(str(entry), str(target))


def iter_supported_platforms() -> Iterable[HostKey]:
    """Used by tests/debug; ordered as the catalog declares."""
    return _CATALOG.keys()
