# Installing dbqm

`pip install dbqm` is the whole story on most machines. This file is for the
rest: installing from source, the platform where some drivers have no wheel,
and what each dependency is there for.

[← Back to the README](../README.md)

---

## Requirements

- Python 3.10+
- Oracle Instant Client (optional, for Oracle connections only) — install it from Settings › Oracle Instant Client, or point dbqm at an existing one there


## Installation

```bash
pip install dbqm
```

That installs the `dbqm` command globally, with the Oracle, PostgreSQL, MySQL
and SQL Server drivers (see [Windows on ARM](#windows-on-arm-win-arm64) for the
one platform where some of them are skipped).

### From source

```bash
git clone https://github.com/silvioricardo87/dbqm.git
cd dbqm
pip install .
```

For development, with the test dependencies:

```bash
pip install -e ".[dev]"
```

### From source (venv)

```bash
git clone https://github.com/silvioricardo87/dbqm.git
cd dbqm

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install .
```

### Windows on ARM (win-arm64)

dbqm's credential encryption uses the same PyCryptodome backend on ARM64,
AMD64 and x86. Its pinned wheel installs on native Windows ARM64 without Rust,
MSVC Build Tools or an emulated Python. Existing Fernet keys, saved passwords
and exported configuration bundles remain compatible; no migration is needed.

Database drivers have separate platform requirements:

| Driver | Native Windows ARM64 | Behavior |
|---|---|---|
| `oracledb` | The driver has ARM64 wheels, but depends on `cryptography`, which stopped publishing them from 46.0.4 | Omitted from the default ARM64 installation. The `oracle` extra still requires a native build toolchain for that dependency. |
| `psycopg[binary]` (PostgreSQL) | No binary wheel | Omitted by default; connections report the missing driver. |
| `pymssql` (SQL Server) | No binary wheel | Omitted by default; connections report the missing driver. |
| `pycryptodome`, `PyMySQL`, `rich`, `textual`, `sqlparse` | Wheels available | Install normally with `pip install dbqm`. |

Native ARM64 installations can use SQLite and MySQL authentication that does
not need RSA (for example, `mysql_native_password`). PyMySQL's full
`sha256_password`/`caching_sha2_password` RSA authentication still needs
`cryptography`; that upstream requirement is unavailable as a current ARM64
wheel. Other platforms retain PyMySQL's `rsa` extra so their existing
authentication behavior does not change. Installing dbqm does not by itself
make the other database drivers available. Python AMD64 under Windows
11 x64 emulation remains an option when those drivers are required, but it is
not needed to install dbqm or use credential encryption.

Windows x86 uses the same encryption backend; the pinned PostgreSQL and SQL
Server drivers also lack win32 wheels, so a full default x86 installation is
not currently covered by the installation guarantee.

### Dependency versions

Direct runtime, extra, development and build requirements use exact versions in
`pyproject.toml`. These pins apply to installations from PyPI; `uv.lock` also
records the transitive dependency versions used in development and CI. A pip
installation can still resolve different transitive versions within the
upstream requirements. Version updates are deliberate changes that must pass
build, lint, tests and the Windows wheel checks.

The Windows CI matrix installs the built wheel outside the checkout on native
ARM64 and AMD64 and forbids source builds for its dependencies. It runs the
Fernet compatibility tests against that installed package. An x86 row verifies
the same encryption backend separately from unavailable database drivers.


## Key Dependencies

| Library | Purpose |
|---------|---------|
| `textual` | Fullscreen TUI framework (layout, widgets, themes) |
| `rich` | Terminal formatting (used by Textual internally + exports) |
| `oracledb` | Oracle database driver |
| `pymssql` | SQL Server database driver |
| `psycopg` | PostgreSQL database driver (v3) |
| `PyMySQL` | MySQL database driver |
| `pycryptodome` | AES for Fernet-compatible credential encryption; HMAC-SHA256 and PBKDF2-HMAC-SHA256 use the Python standard library |
| `sqlparse` | SQL analysis and classification |

## Oracle Instant Client

- **Oracle Instant Client manager** — In-app downloader/installer that detects the host OS/arch and offers compatible Basic packages (Windows x64/x86, macOS ARM64/Intel, Linux x86_64/ARM64) — installed into `~/.dbqm/clients/` and auto-picked up by the thick-mode loader; "Usar este client" pins an install as the configured one. The same operations are on the CLI: `dbqm oracle-client list|available|install|rm` — `install` is the only dbqm command that reaches the internet
- **Configurable Instant Client path** — Settings › Oracle Instant Client stores the client directory in dbqm's own `settings.json`, taking precedence over the system `ORACLE_HOME`. This keeps a 32-bit client wired in by another tool (e.g. an old PL/SQL Developer) from hijacking the 64-bit client dbqm needs. The path is architecture-checked before it is saved, an unusable configured path fails loudly instead of silently falling back, and a failed thick-mode init is reported on connection errors instead of surfacing as a bare network failure
