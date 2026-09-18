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

Several database drivers do not publish wheels for `win-arm64`. dbqm handles each one differently:

| Driver | Status on win-arm64 | Behavior |
|---|---|---|
| `oracledb` | No prebuilt wheel | **Recommended:** install dbqm under Python AMD64 (runs fine via Win11 x64 emulation). Alternative: install MSVC Build Tools and let pip compile from source. |
| `psycopg[binary]` (PostgreSQL) | No prebuilt wheel | Skipped automatically by dependency marker; PostgreSQL connections raise a clear error pointing to manual install. |
| `pymssql` (SQL Server) | No prebuilt wheel | Skipped automatically by dependency marker; SQL Server connections raise a clear error. |
| `cryptography`, `PyMySQL`, `rich`, `textual`, `sqlparse` | Wheels available | Install normally. |

So the path of least resistance on Windows ARM is to use Python AMD64 (the regular installer from python.org), then `pip install dbqm` — everything works via x64 emulation.

If you really want native ARM Python and only need MySQL, skip the Oracle features and install dbqm; Oracle/Postgres/SQL Server connection attempts will fail with a clear hint instead of crashing the CLI.

If you need the optional drivers, try:

```bash
pip install dbqm[postgres]   # PostgreSQL only — requires libpq toolchain on ARM
pip install dbqm[sqlserver]  # SQL Server only — requires FreeTDS toolchain on ARM
```


## Key Dependencies

| Library | Purpose |
|---------|---------|
| `textual` | Fullscreen TUI framework (layout, widgets, themes) |
| `rich` | Terminal formatting (used by Textual internally + exports) |
| `oracledb` | Oracle database driver |
| `pymssql` | SQL Server database driver |
| `psycopg` | PostgreSQL database driver (v3) |
| `PyMySQL` | MySQL database driver |
| `cryptography` | Fernet encryption for credentials |
| `sqlparse` | SQL analysis and classification |

## Oracle Instant Client

- **Oracle Instant Client manager** — In-app downloader/installer that detects the host OS/arch and offers compatible Basic packages (Windows x64/x86, macOS ARM64/Intel, Linux x86_64/ARM64) — installed into `~/.dbqm/clients/` and auto-picked up by the thick-mode loader; "Usar este client" pins an install as the configured one. The same operations are on the CLI: `dbqm oracle-client list|available|install|rm` — `install` is the only dbqm command that reaches the internet
- **Configurable Instant Client path** — Settings › Oracle Instant Client stores the client directory in dbqm's own `settings.json`, taking precedence over the system `ORACLE_HOME`. This keeps a 32-bit client wired in by another tool (e.g. an old PL/SQL Developer) from hijacking the 64-bit client dbqm needs. The path is architecture-checked before it is saved, an unusable configured path fails loudly instead of silently falling back, and a failed thick-mode init is reported on connection errors instead of surfacing as a bare network failure
