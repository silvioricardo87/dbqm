# DB Query Manager (dbqm)

Fullscreen terminal application for managing and executing SQL queries across multiple databases. Supports **Oracle**, **SQL Server**, **PostgreSQL**, and **MySQL**. Built with [Textual](https://textual.textualize.io/) for a modern TUI experience with a single tabbed dashboard, keyboard shortcuts, and theme support.

## Features

- **Fullscreen TUI** — Single tabbed dashboard (8 tabs, `F1`–`F8`), collapsible Templates sidebar, status bar, and keyboard-driven workflow
- **Multi-database query execution** — Run saved queries against Oracle (TNS or direct), SQL Server, PostgreSQL, and MySQL
- **Cross-database comparison** — Execute query groups and compare results side-by-side with match/diff/absent status
- **Report templates** — Define text templates with `{{field}}` placeholders, auto-fill from query results or manual input, export rendered reports
- **DDL execution** — Execute CREATE, ALTER, DROP statements with compilation error detection from USER_ERRORS
- **DDL extraction** — Extract CREATE statements: Oracle (DBMS_METADATA), PostgreSQL (pg_catalog), MySQL (SHOW CREATE)
- **Execute routines** — Run Oracle packages, procedures, and functions with parameter input and DBMS_OUTPUT capture
- **Package editor** — Create and edit Oracle packages with spec/body tabs, inline compilation errors from ALL_ERRORS, and wizard mode
- **Object browser** — Inspect tables, views, stored routines (PostgreSQL/MySQL), and Oracle packages
- **Ad-hoc SQL** — Execute SQL with parameter detection, Ctrl+Enter shortcut, connection validation, and clear with confirmation. Supports CTEs (`WITH ... SELECT`), anonymous PL/SQL blocks (`DECLARE`/`BEGIN`/`END;`, with an optional trailing `/` terminator and leading `--`/`/* */` comments) and the `EXEC`/`EXECUTE`/`CALL <proc>` shortcuts on Oracle, with DBMS_OUTPUT capture displayed after execution (TUI and CLI). In the TUI, a **"Saida DBMS"** checkbox opts SELECT/DML executions into capture; captured logs appear in a dedicated panel below the result with **Save to file** and **Copy to clipboard** buttons (anonymous PL/SQL blocks always show their output). Saving or copying produces an IDE-style **execution evidence** record — the executed SQL, connection, date/time, DBMS_OUTPUT and the outcome — for a self-contained audit trail.
- **Execution plan (`--explain`)** — From the CLI: `dbqm sql "<query>" <conn> --explain` runs `EXPLAIN PLAN FOR` + `DBMS_XPLAN.DISPLAY` on Oracle (or native `EXPLAIN` on PostgreSQL/MySQL) and prints the plan in one step.
- **Dark/Light themes** — "Plano" design system (dark default, light variant), switchable in settings; shared design tokens (`dbqm/design/tokens.py`) drive the TUI, CLI output, and HTML reports so all three stay visually consistent
- **Design tokens** — 15 semantic color tokens (surfaces, text, borda, identidade, and a veredito axis for OK/DIFF/AUSENTE) shared across the TUI, Rich-based CLI output, and HTML report CSS; WCAG contrast-checked against every surface it declares as valid (`VALIDO_SOBRE` in `dbqm/design/tokens.py`). Known gap outside that check: Textual's built-in `$text-muted` and Rich's `[dim]` modifier sit outside the token layer and are not contrast-checked
- **Shared components** — `Dialog` (floating-layer chrome), `EmptyState` (mandatory what/why/first-action for empty lists), `Veredito`/`StatusOperacao` (match/diff/absent + op-result markup), and `Esqueleto` (loading skeleton + distinct disabled/read-only states) are the single implementation for their respective jobs across the TUI; zero literal colors remain outside the token layer, and all four are locked against a second hand-rolled copy reappearing — `Dialog`, `EmptyState` and `Esqueleto` by the component-inventory guards in `tests/design/test_inventory.py`, `Veredito` by its own guard in `tests/ui/test_widgets.py`
- **Layout grammar** — Structure is decided once for the whole TUI, not per screen: `Panel` is the only section frame (a screen taller than the terminal scrolls instead of truncating in silence); navigation follows cardinality (tabs → `Select` with counts → `OptionList` → `DataTable`, with `ListView` out of the vocabulary); a list item is a 2–3 line hierarchy (identity / disambiguation / context) instead of a concatenated string; a result table pins its key column, stripes its rows and scrolls sideways rather than truncating; and actions are anchored to the panel they operate, with destructive ones set apart. Six repo-wide guards in `tests/design/test_layout_inventory.py` enforce it — each one verified by breaking the rule it protects, and each one documenting in code what it cannot see
- **Toggle mapping** — Switch between mapped (DE-PARA) and original values in query and group results
- **Data export** — Export results to CSV, JSON, TXT, HTML reports, and SQL files. Destination is configurable in Settings (defaults to the current working directory); query exports are written flat (no subfolders), while groups/DDL/SQL keep category subfolders by default (togglable). On first export you are prompted to pick a default location.
- **Encrypted credentials** — Passwords stored with Fernet symmetric encryption
- **Connections from the CLI** — `dbqm connection add|update|rm|show|list` creates and edits connections without the TUI, for scripts, CI and AI agents. `--password-stdin` and the `DBQM_PASSWORD` environment variable keep secrets off the command line and out of shell history; `--test` refuses to save a connection that does not answer. `update` changes only the flags you pass — including the password: it is changed only via `--password-stdin` or `--no-password` on that command, never by an ambient `DBQM_PASSWORD` left over from another command. `show` never prints the password. The rules are shared with the TUI (`core/connection_builder.py`), so both front ends validate and default identically.
- **Read-only connections** — mark a connection with `--read-only` (or the "Somente leitura" checkbox in the TUI) and dbqm declines to send it anything but a `SELECT` or a genuine `EXPLAIN`: ad-hoc SQL, explain plans, routine execution and package compilation all refuse, in the TUI as well as the CLI, with a `read_only` error (exit `2`). `--force-write` on `dbqm sql` lifts the refusal for one invocation; it does not imply `--commit`, so writing to a protected connection still takes both flags. Routine execution and package compilation are TUI-only and have no override — clear the mark on the connection instead. This is a rail against mistakes, not a security boundary — see [CHANGELOG.md](./CHANGELOG.md) for what that means and what is deferred.
- **Connection descriptions** — Attach free-form notes to each connection (purpose, schema, contacts); a one-line preview is shown alongside type and destination in the connections list
- **Portable configurations** — Export/import configs as encrypted `.dbqm` bundles
- **Favorites & folders** — Organize queries in folders, star favorites for quick access
- **Query filtering** — On the "Executar consulta" screen, an always-visible filter bar narrows saved queries by free text (name or description) and/or by connection; filters combine (AND) and stack on top of the folder select
- **Paginated results** — Navigate large result sets with next/prev page controls
- **Execution history** — Browse recent executions with timing, row counts, and status
- **Error handling** — Global error modal displays details instead of crashing the app
- **Audit logging** — Opt-in append-only JSON log of all executions
- **Oracle Instant Client manager** — In-app downloader/installer that detects the host OS/arch and offers compatible Basic packages (Windows x64/x86, macOS ARM64/Intel, Linux x86_64/ARM64) — installed into `~/.dbqm/clients/` and auto-picked up by the thick-mode loader; "Usar este client" pins an install as the configured one
- **Configurable Instant Client path** — Settings › Oracle Instant Client stores the client directory in dbqm's own `settings.json`, taking precedence over the system `ORACLE_HOME`. This keeps a 32-bit client wired in by another tool (e.g. an old PL/SQL Developer) from hijacking the 64-bit client dbqm needs. The path is architecture-checked before it is saved, an unusable configured path fails loudly instead of silently falling back, and a failed thick-mode init is reported on connection errors instead of surfacing as a bare network failure

## Changelog

Release history is in [CHANGELOG.md](./CHANGELOG.md).

## Contributing

- [CHANGELOG.md](./CHANGELOG.md) — release history
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — layout, layering, key patterns,
  the TUI layout grammar and its guards, and the recorded known debt
- [docs/ROADMAP.md](./docs/ROADMAP.md) — known bugs first, then what is planned
- [AGENTS.md](./AGENTS.md) — the development workflow, conventions and standards,
  followed by humans and AI agents alike

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

## Usage

### Interactive mode (TUI)

```bash
dbqm
# or
python -m dbqm
```

On first launch, the app creates its data directory (`~/.dbqm`), prompts you to configure your first database connection, and generates an encryption key.

### CLI mode (non-interactive)

```bash
# Show version
dbqm --version

# Execute a saved query (parameters are -p CHAVE=VALOR, repeat for each one)
dbqm run <query-name> -p data_inicio=2026-01-01 -p situacao=PAGO

# Execute a query group (parameters are shared by every query in it)
dbqm run-group <group-name> -p data_inicio=2026-01-01

# Run one ad-hoc SQL across several connections and compare the results
# (at least two -c/--connection; --key overrides the join column)
dbqm multi "SELECT * FROM table" -c prod -c homolog
dbqm multi "SELECT * FROM table" -c prod -c homolog -c staging --key id

# Execute ad-hoc SQL (SELECT/CTE, DML with --commit, DDL, PL/SQL anonymous blocks with DBMS_OUTPUT)
dbqm sql "SELECT * FROM table" <connection>
dbqm sql "WITH x AS (SELECT 1 FROM dual) SELECT * FROM x" <connection>

# Show execution plan (Oracle: EXPLAIN PLAN + DBMS_XPLAN.DISPLAY; PostgreSQL/MySQL: native EXPLAIN)
dbqm sql "SELECT * FROM table WHERE col = :v" <connection> --explain -p v=42

# Test connections
dbqm test [connection]

# List resources
dbqm list connections|queries|groups

# Extract DDL
dbqm ddl <object> <connection>

# List objects by type (TABLE, VIEW, PACKAGE, ROUTINE)
dbqm objects <connection> --type TABLE

# Describe one object: columns, keys and indexes (no row count — see below)
dbqm describe <object> <connection>

# Browse a table, paged
dbqm rows <table> <connection> --limit 20 --offset 0

# Export/Import configs
dbqm export-config
dbqm import-config <file.dbqm>

# View history
dbqm history

# Create a connection (password read from stdin, never from argv)
echo "s3cret" | dbqm connection add prod --type oracle --mode direct \
    --host db.example.com --port 1521 --service ORCL --user admin \
    --password-stdin --test

# Change one field; everything else stays as it was, INCLUDING the password —
# `update` never reads DBQM_PASSWORD, only --password-stdin/--no-password
# change it, and only on this command line
dbqm connection update prod --host db2.example.com
echo "n0v4-s3cret" | dbqm connection update prod --password-stdin

# Inspect and list (the password is redacted)
dbqm connection show prod -f json
dbqm connection list -f json

# Remove (--yes is required when there is no terminal)
dbqm connection rm prod --yes
```

#### Read-only connections

Mark a connection so dbqm refuses anything but a query on it:

```bash
dbqm connection update prod --read-only
dbqm connection update prod --no-read-only   # allow writes again
```

A write is refused before it reaches the driver:

```bash
$ dbqm sql "DELETE FROM t" prod -f json
{"ok": false, "command": "sql", "error": {"code": "read_only", "message": "Conexao 'prod' e somente leitura. Use --force-write para enviar assim mesmo.", "exit": 2}}
$ echo $?
2
```

`--force-write` lifts the refusal for that one invocation — but it does
**not** imply `--commit`, so a write still needs both flags:

```bash
dbqm sql "DELETE FROM t" prod --force-write --commit
```

`--force-write` alone still stops on the ordinary `--commit` check that
every DML statement is subject to, protected connection or not.

### Output format and exit codes

Every command accepts `-f/--format`. `run`, `run-group`, `sql` and `rows`
offer `table|json|csv|raw`; every other command — `test`, `list`, `ddl`,
`history`, `export-config`, `import-config`, `objects`, `describe`, and the
`connection` group — offers `table|json`. `raw` prints plain values with no
headers/decoration, handy for piping the body of a view, package, or
procedure to another tool.
`--export csv|json|txt|html` writes the result to a file regardless of `-f`.
`html` writes a standalone report meant to be read in a browser, and is not
available together with `--flat`.

`-f json` wraps every command in one envelope: a success prints
`{"ok": true, "command": "...", "data": {...}}` to stdout; a failure prints
`{"ok": false, "command": "...", "error": {"code", "message", "exit"}}` to
**stderr**, with stdout left completely empty on failure. Pipe `data`, not
the top level:

```bash
dbqm list connections -f json | jq '.data[].name'

dbqm connection show nada -f json    # nothing on stdout; the error goes to
                                      # stderr; the process exits 2
```

Exit codes are stable across every command:

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | a bug in dbqm — not the input, not the database |
| `2` | usage error, name not found, or a value that fails validation |
| `3` | connection failed |
| `4` | SQL error — the statement reached the driver and was rejected |
| `5` | comparison ran to completion and diverged (`run-group`) |
| `130` | interrupted (Ctrl+C) |

**`run-group` exits `5` when the comparison does not match**, in `-f json`
and in the default `-f table` output alike. Before 2.0.0 it always exited `0`
regardless of the result, so a script chaining `dbqm run-group ... &&
next-step` ran `next-step` unconditionally. It now stops on divergence, which
is the point of running a comparison in a script — see [CHANGELOG.md](./CHANGELOG.md)
for the full migration notes if you scripted against the pre-2.0 shapes.
`dbqm multi` exits `5` on the same terms: the join column it actually used
— the first column common to every connection, or whatever `--key` named —
is reported alongside the comparison, in the `-f json` envelope's
`join_key` field and in the `-f table` header, since a key chosen by a rule
the caller cannot see would turn every number downstream into a guess. A
connection that fails to answer or has its statement rejected stops the
command with nothing exported, rather than comparing whatever subset did
answer.

`export-config` and `import-config` accept `--password-stdin` and the
`DBQM_BUNDLE_PASSWORD` environment variable too, so neither blocks without a
terminal.

### Schema discovery

`objects`, `describe` and `rows` let a script — or an AI agent — see a
database's shape without hand-written catalogue SQL.

```bash
dbqm objects prod --type TABLE
```

```json
{"ok": true, "command": "objects", "data": {"connection_name": "prod", "obj_type": "TABLE", "objects": ["ACESSO_EXTERNO_LOG", "ACESSO_EXTERNO_USUARIO", "..."]}}
```

(the `objects` array lists every name; truncated above for brevity.)

```bash
dbqm describe ACESSO_EXTERNO_USUARIO prod
```

```
ACESSO_EXTERNO_USUARIO (TABLE)
+--------------------------------------+
| Coluna      | Tipo    | Nulo | Chave |
|-------------+---------+------+-------|
| CD_SUSEP    | varchar | NAO  | PK    |
| CD_CORRETOR | numeric | NAO  | PK    |
| CD_IP       | varchar | NAO  | PK    |
| CD_OPCAO    | numeric | SIM  |       |
+--------------------------------------+

INDICES
  PK_ACESSO_EXTERNO_USUARIO  UNIQUE (CD_CORRETOR, CD_SUSEP, CD_IP)
```

`-f json` carries the same content — columns (each with `data_type`,
`nullable`, `is_pk`, `fk_ref`) and `indexes`, plus `object_type` (`"TABLE"` or
`"VIEW"`) and, for a view, `sql_definition`. **Neither format shows a row
count** — a `COUNT(*)` is a full scan, and a describe is meant to be instant
(`psql \d` shows none either):

```json
{"ok": true, "command": "describe", "data": {"table": "ACESSO_EXTERNO_USUARIO", "columns": [{"name": "CD_SUSEP", "data_type": "varchar", "nullable": false, "is_pk": true, "fk_ref": ""}], "indexes": [{"name": "PK_ACESSO_EXTERNO_USUARIO", "columns": ["CD_CORRETOR", "CD_SUSEP", "CD_IP"], "is_unique": true}], "connection_name": "prod", "object_type": "TABLE"}}
```

```bash
dbqm rows ACESSO_EXTERNO_USUARIO prod --limit 3
```

```
+---------------------------------------------------------+
| cd_susep       | cd_corretor | cd_ip         | cd_opcao |
|----------------+-------------+---------------+----------|
| 00000100370631 | 1026        | 104.41.10.105 |          |
| 00000100617482 | 4031        | 104.41.10.105 |          |
| 00000100617482 | 4031        | 162.144.82.47 |          |
+---------------------------------------------------------+
3 registros em 0.61s
Mostrando 3 de 1607 linhas. Use --offset 3 para as proximas.
```

`rows` are parallel arrays, matching `run`/`sql` since 2.0.0; `-f json` also
carries `total_count`, `limit` and `offset` so a script can page without
parsing the table footer:

```json
{"ok": true, "command": "rows", "data": {"table": "ACESSO_EXTERNO_USUARIO", "connection_name": "prod", "columns": ["cd_susep", "cd_corretor", "cd_ip", "cd_opcao"], "rows": [["00000100370631", "1026", "104.41.10.105", null], ["00000100617482", "4031", "104.41.10.105", null], ["00000100617482", "4031", "162.144.82.47", null]], "row_count": 3, "total_count": 1607, "limit": 3, "offset": 0}}
```

There is deliberately no `--where` on `rows`: `dbqm sql` already takes a
predicate.

### Export destination

Exports go to the current working directory by default. The first time you press `Exportar` in the UI, dbqm shows a setup modal so you can pick a fixed default directory or keep using the CWD. You can change it later in Settings → Exportacao. Two options live there:

- **Diretorio de exportacao** — empty means "use CWD"; any custom path must already exist.
- **Criar subdiretorios por tipo** (ON by default) — controls whether group/DDL/SQL exports nest under `grupos/`, `ddl/`, etc. Query results (`consultas`) always go flat in the resolved directory.

The CLI uses the same setting (no modal).

### Data directory

DBQM stores all configuration, credentials, and exports under `~/.dbqm/` by default. Override with the `DBQM_HOME` environment variable:

```bash
export DBQM_HOME=/path/to/custom/dir
dbqm
```

## Keyboard Navigation

The application is fully keyboard-driven:

| Key | Action | Context |
|-----|--------|---------|
| `F1`–`F8` | Switch dashboard tab | Global |
| `↑` `↓` | Navigate items / widgets | Lists, tables, forms |
| `Enter` | Select / Confirm | Global |
| `Escape` | Go back | Global |
| `Ctrl+B` | Toggle Templates sidebar | Global |
| `Ctrl+Q` | Quit | Global |
| `/` | Search / filter | Lists |
| `?` | Help (shortcuts) | Global |
| `Tab` | Next widget | Forms, settings |
| `V` | Vertical view | Query results |
| `E` | Export | Query/group results |
| `R` | Re-execute | Query/group results |
| `M` | Toggle mapped/original values | Query/group results |
| `F` | Toggle flat/pivoted | Group results |
| `S` | Filter by status | Group results |
| `H` | HTML report | Group results |
| `Ctrl+Enter` | Execute SQL | Ad-hoc SQL |
| `Ctrl+L` | Clear SQL input | Ad-hoc SQL |
| `X` | Clear history | History |
| `N` | New item | Connections, queries |
| `D` | Delete / Details | Connections, history |
| `C` | Compile Spec | Package editor |
| `B` | Compile Body | Package editor |

## Dashboard tabs

The app is a single tabbed dashboard. Switch tabs with `F1`–`F8`:

| Key | Tab | Content |
|-----|-----|---------|
| `F1` | 🔍  Coleta | Ad-hoc SQL |
| `F2` | 🔌  Conexoes | Manage database connections |
| `F3` | 📂  Objetos | Object browser |
| `F4` | 📊  Multi-Exec | Run one ad-hoc SQL across selected connections & compare (load/save as a group) |
| `F5` | 📜  Historico | Execution history |
| `F6` | ⚙️  Configuracoes | Settings (inclui Exportar/Importar) |
| `F7` | 📝  Consultas | Run saved queries |
| `F8` | 🧰  Ferramentas | Gerenciar Grupos/Templates, Package editor, Executar Rotina |

A collapsible **Templates** sidebar (`Ctrl+B`) lists saved SQL templates; choosing one injects its SQL into the active tab's editor.

Above the status bar, a contextual **action bar** shows the actions available on the current screen with their shortcut keys (`N Nova`, `T Testar`, …); the entries are clickable too. Screens that open a deeper screen inside their own tab — Configuracoes › Oracle Instant Clients and Configuracoes › Exportar / Importar — announce `Esc Voltar` there, which is how you go back.

## Query Groups & Comparison

Groups run the same logical query across multiple databases and compare results:

- Define a **join key** (row identifier) and **comparison columns**
- Optional **normalization mapping** for semantic equivalence (e.g., "paga" = "pago")
- Optional **column mapping** for mismatched column names
- Results show status per row: `OK`, `DIFF`, `ABSENT`
- Two display modes: **flat** (one table per column) and **pivoted** (one table per key)
- Filter results by status (divergent, absent, or combined)
- Export as HTML report with interactive filters
- **Report templates**: attach a template to a group, configure field sources (auto from query results or manual input), and render formatted reports after execution

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

## Security

- Database passwords encrypted at rest using Fernet (`.dbqm_key` master key)
- Configuration bundles use PBKDF2 (480,000 iterations) + Fernet
- Queries use bind variables to prevent SQL injection
- SQL identifiers validated against allowlist pattern
- Query results capped at 10,000 rows
- Config bundle imports limited to 10 MB
- HTML reports escape all user-controlled values
- Audit log files created with restricted permissions
- File open operations restricted to exports directory
