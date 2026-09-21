# dbqm — Database Query Manager

[![PyPI](https://img.shields.io/pypi/v/dbqm)](https://pypi.org/project/dbqm/)
[![Python](https://img.shields.io/pypi/pyversions/dbqm)](https://pypi.org/project/dbqm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](https://github.com/silvioricardo87/dbqm/blob/main/LICENSE)
[![Downloads](https://img.shields.io/pepy/dt/dbqm)](https://pepy.tech/project/dbqm)

A fullscreen terminal app **and** a scriptable CLI for running SQL across
**Oracle**, **SQL Server**, **PostgreSQL**, **MySQL** and **SQLite** — from one
place, with one set of saved connections.

Built with [Textual](https://textual.textualize.io/). Credentials are encrypted
at rest; nothing is ever written to your shell history.

📖 **[Full documentation on GitHub](https://github.com/silvioricardo87/dbqm)**

---

## Install

```bash
pip install dbqm
```

Python 3.10+. Database drivers come with it, and SQLite needs none — it is
in the standard library, so `dbqm connection add local --type sqlite --database
./app.db --no-password` works on a fresh install with nothing else to set up.

> **Windows on ARM:** some drivers have no `win-arm64` wheel and are skipped
> automatically. Use Python AMD64 (it runs under x64 emulation) — see the
> [installation notes](https://github.com/silvioricardo87/dbqm/blob/main/docs/INSTALL.md#windows-on-arm-win-arm64).

Oracle connections additionally need the Oracle Instant Client. dbqm can
download and install it for you from **Settings › Oracle Instant Client**.

`pip install "dbqm[mcp]"` additionally installs the MCP server for AI agents
(`dbqm mcp`) — see [docs/MCP.md](https://github.com/silvioricardo87/dbqm/blob/main/docs/MCP.md).

## Use it interactively

```bash
dbqm tui
```

An eight-tab dashboard (`F1`–`F8`): collect, connections, objects, multi-exec,
history, settings, queries and tools. Fully keyboard-driven, dark and light
themes.

On first use it creates `~/.dbqm/`, generates an encryption key and walks you
through your first connection. A bare `dbqm`, no arguments, prints the help
instead of opening this.

## Use it from a script

Every command but `dbqm tui` is non-interactive — no prompts, no TTY required, and
`-f json` everywhere — which is what makes dbqm usable from a script, from CI
or from an AI agent. `dbqm describe-cli -f json` reports the whole surface,
read live from the parser.

```bash
# Create a connection -- one shape per engine, the password piped rather
# than passed in argv, and the port defaulted when you leave it out
# (1433 SQL Server, 3306 MySQL, 5432 PostgreSQL, 1521 Oracle).
echo "s3cret" | dbqm connection add mssql-prod --type sqlserver \
    --host sql.example.com --database Sales --user sa --password-stdin

echo "s3cret" | dbqm connection add mysql-prod --type mysql \
    --host db.example.com --database shop --user app --password-stdin

echo "s3cret" | dbqm connection add prod --type oracle --mode direct \
    --host db.example.com --port 1521 --service ORCL --user admin \
    --password-stdin --test

# Run SQL. -f json for a machine, -f raw to pipe a CLOB somewhere else.
dbqm sql "SELECT * FROM orders WHERE status = :s" prod -p s=PAID -f json

# Save a query once, run it with different parameters later.
dbqm run open-orders -p start_date=2026-01-01

# Compare the same logical query across environments.
dbqm run-group daily-reconciliation -p day=2026-01-01

# Or compare one ad-hoc statement across connections -- including across
# DIFFERENT ENGINES -- without saving anything. Exits 5 when they diverge,
# so a script can branch on the verdict.
dbqm multi "SELECT id, total FROM orders WHERE day = :d" \
    -c oracle-prod -c postgres-replica -p d=2026-01-01 -f json

# Call an Oracle routine, with OUT parameters and the return value as data.
dbqm call PKG_BILLING.CLOSE_MONTH <conn> -p p_month=1 --commit -f json

# Get an execution plan in one step (no EXPLAIN PLAN FOR boilerplate).
dbqm sql "SELECT * FROM orders WHERE customer_id = :id" prod --explain -p id=42

# See a database's shape: what exists, one object's columns/keys/indexes,
# and a table's rows, paged.
dbqm objects prod --type TABLE
dbqm describe orders prod
dbqm rows orders prod --limit 20

# Extract DDL, browse connections, review history.
dbqm ddl PKG_BILLING prod
dbqm connection list -f json
dbqm history -n 20
```

`--help` on any command lists its flags.

## What it does

- **Saved queries with parameters**, organised in folders, with favourites and
  a value mapping for codes that differ between systems.
- **Cross-database comparison** — run the same logical query against several
  connections and get a per-row `OK` / `DIFF` / `ABSENT` verdict, as a table or
  an interactive HTML report.
- **Object browser** — tables, views, routines and Oracle packages: columns,
  primary keys, foreign keys and indexes, without writing catalogue SQL. Works
  on every engine, SQLite included, which makes it a zero-setup way to try the
  whole tool against a local file.
- **Ad-hoc SQL** — SELECT, CTEs, DML, DDL with compilation-error detection, and
  anonymous PL/SQL blocks with `DBMS_OUTPUT` captured and shown.
- **Execute routines** — packages, procedures and functions, with parameter
  input and output capture.
- **Package editor** for Oracle PL/SQL, with inline compilation errors.
- **Read-only connections** — mark a connection so dbqm refuses anything but a query on it, with a one-invocation `--force-write` override for `dbqm sql`.
- **Exports** — CSV, JSON, TXT, SQL and HTML reports, plus IDE-style execution
  evidence (the SQL, the connection, the timestamp, the outcome) for an audit
  trail you can hand to someone else.
- **Portable configuration** — export and import your connections and queries as
  an encrypted `.dbqm` bundle.
- **English and Portuguese** — every screen, message and `--help` string is
  translated; `dbqm config set language pt`, or `DBQM_LANG=pt` for one run.

## Security

- Connection passwords are encrypted at rest with Fernet.
- Passwords are read from stdin or an environment variable, never from `argv` —
  they do not reach your shell history or the process table.
- Queries use bind variables; SQL identifiers are validated against an allowlist.
- HTML reports escape every user-controlled value.

## Links

- **[Repository and full README](https://github.com/silvioricardo87/dbqm)**
- [Changelog](https://github.com/silvioricardo87/dbqm/blob/main/CHANGELOG.md)
- [Roadmap and known bugs](https://github.com/silvioricardo87/dbqm/blob/main/docs/ROADMAP.md)
- [Report an issue](https://github.com/silvioricardo87/dbqm/issues)

MIT licensed.
