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
- **Shared components** — `Dialog` (floating-layer chrome), `EmptyState` (mandatory what/why/first-action for empty lists), `Veredito`/`StatusOperacao` (match/diff/absent + op-result markup), and `Esqueleto` (loading skeleton + distinct disabled/read-only states) are the single implementation for their respective jobs across the TUI; zero literal colors remain outside the token layer, and a component-inventory test locks all four against a second hand-rolled copy reappearing
- **Layout grammar** — Structure is decided once for the whole TUI, not per screen: `Panel` is the only section frame (a screen taller than the terminal scrolls instead of truncating in silence); navigation follows cardinality (tabs → `Select` with counts → `OptionList` → `DataTable`, with `ListView` out of the vocabulary); a list item is a 2–3 line hierarchy (identity / disambiguation / context) instead of a concatenated string; a result table pins its key column, stripes its rows and scrolls sideways rather than truncating; and actions are anchored to the panel they operate, with destructive ones set apart. Six repo-wide guards in `tests/design/test_inventario_layout.py` enforce it — each one verified by breaking the rule it protects, and each one documenting in code what it cannot see
- **Toggle mapping** — Switch between mapped (DE-PARA) and original values in query and group results
- **Data export** — Export results to CSV, JSON, TXT, PNG, HTML reports, and SQL files. Destination is configurable in Settings (defaults to the current working directory); query exports are written flat (no subfolders), while groups/DDL/SQL keep category subfolders by default (togglable). On first export you are prompted to pick a default location.
- **Encrypted credentials** — Passwords stored with Fernet symmetric encryption
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

## Requirements

- Python 3.10+
- Oracle Instant Client (optional, for Oracle connections only) — install it from Settings › Oracle Instant Client, or point dbqm at an existing one there

## Installation

### From source (pip install)

```bash
git clone https://github.com/silvioricardo87/dbqm.git
cd dbqm
pip install .
```

This installs the `dbqm` command globally. For development:

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

pip install -r requirements.txt
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

# Execute a saved query
dbqm run <query-name> --param1 value1

# Execute a query group
dbqm run-group <group-name> --param1 value1

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

# Export/Import configs
dbqm export-config
dbqm import-config <file.dbqm>

# View history
dbqm history
```

Output format options: `--format table|json|csv|raw` and `--export csv|json|txt`. Use `raw` to print plain values (CLOB/LONG materialized, no headers/decoration) — handy for piping the body of a view, package, or procedure to another tool.

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

## Project Structure

```
dbqm/
├── pyproject.toml                 # Package metadata & dependencies
├── main.py                        # Legacy entry point (delegates to dbqm.main)
├── requirements.txt               # Dependencies (alternative to pyproject.toml)
├── dbqm/
│   ├── _version.py                # Package version
│   ├── main.py                    # Entry point (TUI + CLI dispatch)
│   ├── __main__.py                # python -m dbqm support
│   ├── cli.py                     # Non-interactive CLI
│   ├── design/
│   │   └── tokens.py               # Design tokens — one source consumed by TUI, CLI and HTML report
│   ├── ui/
│   │   ├── app.py                 # Main Textual App (layout, routing, keybindings)
│   │   ├── theme.py               # Plano Dark/Light theme definitions (built on dbqm/design/tokens.py)
│   │   ├── utils.py               # sanitize_id, escape_markup utilities
│   │   ├── screens/               # Screen widgets (one per feature)
│   │   │   ├── query_exec.py      # Execute saved query
│   │   │   ├── query_manage.py    # Query CRUD, DE-PARA, SQL viewer
│   │   │   ├── group_exec.py      # Execute group comparison
│   │   │   ├── group_manage.py    # Group CRUD
│   │   │   ├── template_manage.py # Template CRUD
│   │   │   ├── adhoc.py           # Ad-hoc SQL execution
│   │   │   ├── ddl.py             # DDL extraction
│   │   │   ├── exec_routine.py     # Execute packages, procedures, functions
│   │   │   ├── browser.py         # Object browser (tables, views, packages)
│   │   │   ├── history.py         # Execution history
│   │   │   ├── connections.py     # Connection management
│   │   │   ├── package_editor.py   # Oracle package editor (spec/body, compile)
│   │   │   ├── settings.py        # Theme, audit toggle, export/import
│   │   │   ├── config_port.py     # Config export/import (used by settings)
│   │   │   └── oracle_clients.py  # Download/extract/remove Oracle Instant Clients
│   │   ├── widgets/               # Reusable UI components
│   │   │   ├── templates_sidebar.py  # Collapsible templates sidebar with keyboard nav
│   │   │   ├── breadcrumb.py      # Navigation breadcrumb
│   │   │   ├── result_table.py    # DataTable with pinned key column, zebra, pagination + record mode
│   │   │   ├── query_list.py      # Query OptionList with search/filter
│   │   │   ├── group_result.py    # Flat/pivoted comparison display
│   │   │   ├── sql_viewer.py      # Syntax-highlighted SQL display
│   │   │   ├── action_bar.py      # Contextual keyboard shortcuts bar
│   │   │   ├── status_bar.py      # Connection status + counters
│   │   │   ├── progress.py        # Loading indicator
│   │   │   ├── panel.py           # Bordered panel consuming $painel/$borda tokens — the only section frame
│   │   │   ├── lista_hierarquica.py  # item_hierarquico — 2-3 line list item (identity/disambiguation/context)
│   │   │   ├── dialog.py          # Dialog chrome for floating layers (replaces 29 hand-copied frames)
│   │   │   ├── empty_state.py     # EmptyState — mandatory "what/why/first action" for empty lists
│   │   │   ├── veredito.py        # Veredito/StatusOperacao markup (match/diff/absent, op result color)
│   │   │   └── esqueleto.py       # Loading skeleton + distinct disabled/read-only states
│   │   ├── modals/                # Dialog screens
│   │   │   ├── param_input.py     # Query parameter input
│   │   │   ├── confirm.py         # Yes/No confirmation
│   │   │   ├── text_input.py      # Single text input
│   │   │   ├── export_picker.py   # Export format selector
│   │   │   ├── export_dir_setup.py     # Default export directory
│   │   │   ├── oracle_client_dir.py    # Oracle Instant Client directory
│   │   │   ├── column_maps.py     # DE-PARA value mapping
│   │   │   ├── error.py           # Error display modal
│   │   │   └── help.py            # Keyboard shortcuts overlay
│   │   └── legacy/
│   │       └── display.py         # Rich renderables for PNG/TXT export
│   ├── core/                      # Business logic (database-agnostic)
│   │   ├── paths.py               # Centralized path resolution (~/.dbqm)
│   │   ├── db_manager.py          # Connection handling
│   │   ├── query_engine.py        # SQL execution + parameter binding
│   │   ├── group_engine.py        # Multi-database comparison
│   │   ├── exporter.py            # Export (CSV, JSON, TXT, PNG)
│   │   ├── html_report.py         # HTML comparison reports
│   │   ├── ddl_extractor.py       # Oracle DDL (DBMS_METADATA)
│   │   ├── ddl_pg.py              # PostgreSQL DDL
│   │   ├── ddl_mysql.py           # MySQL DDL
│   │   ├── object_browser.py      # Database object introspection
│   │   ├── table_browser.py       # Table data browsing
│   │   ├── package_editor.py       # Oracle package compile + errors
│   │   ├── crypto.py              # Password encryption
│   │   ├── config_portability.py  # Config import/export
│   │   ├── history.py             # Execution history
│   │   ├── oracle_client_installer.py  # Detect host + download/extract Oracle Instant Client
│   │   └── audit.py               # Audit logging
│   └── models/                    # Data models (JSON persistence)
│       ├── connection.py          # Connection config
│       ├── query.py               # Query definition
│       ├── group.py               # Query group config
│       └── settings.py            # App settings (theme, audit)
├── config/                        # JSON configs (gitignored)
├── exports/                       # Generated output files (gitignored)
└── tests/                         # Test suite (931 tests)
    ├── core/                      # Core logic tests
    ├── models/                    # Model tests
    ├── design/                    # Design-system guards (color tokens, contrast, layout grammar)
    └── ui/                        # TUI widget/screen/modal tests
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
| `Pillow` | PNG screenshot export |

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
