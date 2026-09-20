# DB Query Manager (dbqm)

[![PyPI](https://img.shields.io/pypi/v/dbqm)](https://pypi.org/project/dbqm/)
[![Python](https://img.shields.io/pypi/pyversions/dbqm)](https://pypi.org/project/dbqm/)
[![Checks](https://github.com/silvioricardo87/dbqm/actions/workflows/checks.yml/badge.svg?branch=main)](https://github.com/silvioricardo87/dbqm/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue)](./LICENSE)
[![Downloads](https://img.shields.io/pepy/dt/dbqm)](https://pepy.tech/project/dbqm)

**One tool, five databases, two front ends.** A scriptable CLI and a fullscreen
terminal application for running SQL across **Oracle**, **SQL Server**,
**PostgreSQL**, **MySQL** and **SQLite** — from one place, with one set of
saved connections.

Every operation works without a TTY, so the same tool serves a person at a
terminal, a shell script, a CI job and an AI agent.

```bash
pip install dbqm
```

## One set of connections, five engines

The point of dbqm is that the engine stops mattering. A connection is a name;
the same command, the same flags and the same JSON envelope work against all
five, and the differences that cannot be hidden are listed rather than
pretended away.

| | Oracle | SQL Server | PostgreSQL | MySQL | SQLite |
|---|:--:|:--:|:--:|:--:|:--:|
| Queries, DML, parameters, export | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cross-database comparison | ✅ | ✅ | ✅ | ✅ | ✅ |
| Objects, describe, paged rows | ✅ | ✅ | ✅ | ✅ | ✅ |
| DDL extraction | `DBMS_METADATA` | — | `pg_catalog` | `SHOW CREATE` | `sqlite_master` |
| Execution plans | `DBMS_XPLAN` | — | `EXPLAIN` | `EXPLAIN` | `EXPLAIN QUERY PLAN` |
| Stored routines (`dbqm call`) | ✅ | — | — | — | — |
| Packages and the package editor | ✅ | — | — | — | — |
| Read-only enforced by the server | per transaction | — (dbqm only) | ✅ | ✅ | ✅ |
| Driver needed | Instant Client | bundled | bundled | bundled | none |

The comparison is the reason the list matters: `dbqm multi` runs **one**
statement against connections on **different engines** and reports a per-row
`OK` / `DIFF` / `ABSENT` verdict, exiting `5` when they diverge. Comparing
Oracle production against a PostgreSQL replica is the ordinary case, not a
special one.

## The CLI

```bash
# One shape of command per engine. The password is piped, never in argv,
# and the port is the engine's default when you leave it out.
echo "s3cret" | dbqm connection add mssql-prod --type sqlserver \
    --host sql.example.com --database Sales --user sa --password-stdin

echo "s3cret" | dbqm connection add mysql-prod --type mysql \
    --host db.example.com --database shop --user app --password-stdin

# A SQLite file needs nothing but its path — no host, no user, no password.
dbqm connection add local --type sqlite --database ./app.db --no-password

# Run SQL. -f json for a machine, -f raw to pipe a CLOB somewhere else.
dbqm sql "SELECT * FROM orders WHERE status = :s" local -p s=PAID -f json

# Save a query once, run it with different parameters later.
dbqm run open-orders -p start_date=2026-01-01

# Compare one statement across connections. Exits 5 when they diverge.
dbqm multi "SELECT id, total FROM orders" -c prod -c staging -f json

# See a database's shape without writing catalogue SQL.
dbqm objects prod --type TABLE
dbqm describe orders prod
dbqm rows orders prod --limit 20
```

Twenty-one commands, and **not one of them needs a terminal**: no prompts you
cannot answer with a flag, no output you cannot get as JSON. That is what makes
dbqm usable from a script, from CI, or from an agent.

- **One envelope for every command.** Success prints
  `{"ok": true, "command": "...", "data": {...}}` on stdout; failure prints
  `{"ok": false, ..., "error": {"code", "message", "exit"}}` on **stderr**,
  leaving stdout empty. Pipe `.data`, never the top level.
- **Exit codes that mean something** — `2` usage or not found, `3` connection
  failed, `4` SQL rejected by the driver, `5` a comparison that diverged. A
  script can branch on the number without parsing text.
- **Passwords never in `argv`** — `--password-stdin` or an environment
  variable, so they stay out of shell history and the process table.
- **It describes itself.** `dbqm describe-cli -f json` reports every command,
  subcommand and flag, read live from the parser rather than from a list
  someone has to remember to update — which is how an agent learns the surface
  without a human writing it down.

Every command, every flag, the envelope and the exit codes:
**[docs/CLI.md](./docs/CLI.md)**.

## The terminal application

```bash
dbqm
```

![A saved query running against a connection, with its result table](docs/img/queries.svg)

Eight tabs (`F1`–`F8`), in order: collect, connections, objects, multi-exec,
history, settings, queries and tools. On first launch it creates `~/.dbqm/`,
generates an encryption key and walks you through your first connection. Keys,
tabs and the comparison screens: **[docs/TUI.md](./docs/TUI.md)**.

![The same statement run against two databases, reported as DIVERGENT with per-column counts](docs/img/comparison.svg)

## What it does

**Run and compare**

- **Saved queries** with named parameters, folders, favourites and a value
  mapping for codes that differ between systems
- **Cross-database comparison** — the same logical query against several
  connections, as a table or an interactive HTML report. `dbqm multi` does it
  for one ad-hoc statement, without saving anything
- **Ad-hoc SQL** — SELECT, CTEs, DML with `--commit`, DDL with
  compilation-error detection, and anonymous PL/SQL blocks with `DBMS_OUTPUT`
  captured and shown
- **Execution plans** — `dbqm sql "<query>" <conn> --explain`, in one step
- **Execute routines** — Oracle packages, procedures and functions, with
  parameters in, and OUT values and the return value back as data

**Look around**

- **Object browser** — tables, views and their columns, primary keys, foreign
  keys and indexes on all five engines; routines on the four that have them,
  packages on Oracle
- **Schema discovery from the CLI** — `objects`, `describe` and `rows`, paged
- **DDL extraction** — Oracle, PostgreSQL, MySQL and SQLite (see the table
  above; SQL Server is the gap)
- **Package editor** for Oracle PL/SQL, with inline compilation errors
- **Execution history** with timing, row counts and status

**Curate without the TUI**

- `dbqm connection|query|group|template add|update|show|rm|list` — the same
  validation both front ends use, `-f json` everywhere, `update` changes only
  the flags you pass
- `dbqm config get|set|list` — valid keys and themes are read at runtime, so
  neither list can go stale; a bad value is refused, not coerced
- **Portable configuration** — export and import as an encrypted `.dbqm` bundle

**Stay out of trouble**

- **Read-only connections** — mark one and dbqm declines to send it anything
  but a query, with a one-invocation `--force-write` override for `dbqm sql`
- **Encrypted credentials** — Fernet at rest; passwords read from stdin or the
  environment, never from `argv`
- **Exports** — CSV, JSON, TXT, HTML and SQL, plus IDE-style execution evidence
  (the SQL, the connection, the timestamp, the outcome) for an audit trail
- **Audit logging** — opt-in, append-only JSON
- **English and Portuguese** — every screen, message and `--help` string comes
  from a catalogue; `dbqm config set language pt`, or `DBQM_LANG` for one run

Where dbqm keeps its files, where exports land and which language it speaks:
**[docs/CONFIGURATION.md](./docs/CONFIGURATION.md)**.

## Install

```bash
pip install dbqm
```

Python 3.10+. The drivers come with it, and SQLite needs none — it is in the
standard library. Oracle connections additionally need the Oracle Instant
Client, which dbqm can download for you from Settings › Oracle Instant Client,
or from the CLI with `dbqm oracle-client install`.

Installing from source, the `win-arm64` caveats and what each dependency is
for: **[docs/INSTALL.md](./docs/INSTALL.md)**.

## Security

- Database passwords encrypted at rest using Fernet (`.dbqm_key` master key)
- Configuration bundles use PBKDF2 (480,000 iterations) + Fernet
- Queries use bind variables; SQL identifiers validated against an allowlist
- Query results capped at 10,000 rows; bundle imports limited to 10 MB
- HTML reports escape all user-controlled values
- Audit log files created with restricted permissions
- File open operations restricted to the exports directory

Read-only connections are a rail against mistakes, not a security boundary —
[CHANGELOG.md](./CHANGELOG.md) says what that means and what is deferred.

## Documentation

| | |
|---|---|
| [docs/CLI.md](./docs/CLI.md) | Every command, the JSON envelope, exit codes |
| [docs/TUI.md](./docs/TUI.md) | Tabs, keyboard map, comparison screens |
| [docs/INSTALL.md](./docs/INSTALL.md) | From source, `win-arm64`, dependencies |
| [docs/CONFIGURATION.md](./docs/CONFIGURATION.md) | Data directory, export destination, language |
| [CHANGELOG.md](./CHANGELOG.md) | Release history |
| [docs/ROADMAP.md](./docs/ROADMAP.md) | Known bugs first, then what is planned |
| [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) | Layout, layering, patterns, recorded debt |
| [AGENTS.md](./AGENTS.md) | The development workflow, for humans and agents alike |

[MIT licensed](./LICENSE).
