# dbqm — Database Query Manager

[![PyPI Downloads](https://img.shields.io/pepy/dt/dbqm)](https://pepy.tech/project/dbqm)

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
./meu.db --no-password` works on a fresh install with nothing else to set up.

> **Windows on ARM:** some drivers have no `win-arm64` wheel and are skipped
> automatically. Use Python AMD64 (it runs under x64 emulation) — see the
> [README](https://github.com/silvioricardo87/dbqm#windows-on-arm-win-arm64).

Oracle connections additionally need the Oracle Instant Client. dbqm can
download and install it for you from **Settings › Oracle Instant Client**.

## Use it interactively

```bash
dbqm
```

An eight-tab dashboard (`F1`–`F8`): ad-hoc SQL, connections, an object browser,
multi-database comparison, history, saved queries and tools. Fully
keyboard-driven, dark and light themes.

On first launch it creates `~/.dbqm/`, generates an encryption key and walks you
through your first connection.

## Use it from a script

Every operation below is non-interactive — no prompts, no TTY required, which is
what makes dbqm usable from CI or from an AI agent.

```bash
# Create a connection. The password is piped, never passed in argv.
echo "s3cret" | dbqm connection add prod --type oracle --mode direct \
    --host db.example.com --port 1521 --service ORCL --user admin \
    --password-stdin --test

# Run SQL. -f json for a machine, -f raw to pipe a CLOB somewhere else.
dbqm sql "SELECT * FROM pedidos WHERE status = :s" prod -p s=PAGO -f json

# Save a query once, run it with different parameters later.
dbqm run pedidos-em-aberto -p data_inicio=2026-01-01

# Compare the same logical query across environments.
dbqm run-group conciliacao-diaria -p data=2026-01-01

# Or compare one ad-hoc statement across connections, without saving anything.
# Exits 5 when they diverge, so a script can branch on the verdict.
dbqm multi "SELECT id, total FROM pedidos WHERE dia = :d" \
    -c prod -c homolog -p d=2026-01-01 -f json

# Call an Oracle routine, with OUT parameters and the return value as data.
dbqm call PKG_FATURAMENTO.FECHAR <conn> -p p_mes=1 --commit -f json

# Get an execution plan in one step (no EXPLAIN PLAN FOR boilerplate).
dbqm sql "SELECT * FROM pedidos WHERE cliente_id = :id" prod --explain -p id=42

# See a database's shape: what exists, one object's columns/keys/indexes,
# and a table's rows, paged.
dbqm objects prod --type TABLE
dbqm describe pedidos prod
dbqm rows pedidos prod --limit 20

# Extract DDL, browse connections, review history.
dbqm ddl PKG_FATURAMENTO prod
dbqm connection list -f json
dbqm history -n 20
```

`--help` on any command lists its flags.

## What it does

- **Saved queries with parameters**, organised in folders, with favourites and
  a DE-PARA column mapping for values that differ between systems.
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
