# DB Query Manager (dbqm)

Fullscreen terminal application for managing and executing SQL queries across multiple databases. Supports **Oracle**, **SQL Server**, **PostgreSQL**, and **MySQL**. Built with [Textual](https://textual.textualize.io/) for a modern TUI experience with sidebar navigation, keyboard shortcuts, and theme support.

## Features

- **Fullscreen TUI** — Fixed layout with sidebar navigation, breadcrumb, status bar, and keyboard-driven workflow
- **Multi-database query execution** — Run saved queries against Oracle (TNS or direct), SQL Server, PostgreSQL, and MySQL
- **Cross-database comparison** — Execute query groups and compare results side-by-side with match/diff/absent status
- **Report templates** — Define text templates with `{{field}}` placeholders, auto-fill from query results or manual input, export rendered reports
- **DDL execution** — Execute CREATE, ALTER, DROP statements with compilation error detection from USER_ERRORS
- **DDL extraction** — Extract CREATE statements: Oracle (DBMS_METADATA), PostgreSQL (pg_catalog), MySQL (SHOW CREATE)
- **Execute routines** — Run Oracle packages, procedures, and functions with parameter input and DBMS_OUTPUT capture
- **Package editor** — Create and edit Oracle packages with spec/body tabs, inline compilation errors from ALL_ERRORS, and wizard mode
- **Object browser** — Inspect tables, views, stored routines (PostgreSQL/MySQL), and Oracle packages
- **Ad-hoc SQL** — Execute SQL with parameter detection, Ctrl+Enter shortcut, connection validation, and clear with confirmation
- **Dark/Light themes** — GitHub Dark (default) and GitHub Light, switchable in settings
- **Toggle mapping** — Switch between mapped (DE-PARA) and original values in query and group results
- **Data export** — Export results to current directory as CSV, JSON, TXT, PNG, HTML reports, and SQL files
- **Encrypted credentials** — Passwords stored with Fernet symmetric encryption
- **Portable configurations** — Export/import configs as encrypted `.dbqm` bundles
- **Favorites & folders** — Organize queries in folders, star favorites for quick access
- **Paginated results** — Navigate large result sets with next/prev page controls
- **Execution history** — Browse recent executions with timing, row counts, and status
- **Error handling** — Global error modal displays details instead of crashing the app
- **Audit logging** — Opt-in append-only JSON log of all executions

## Requirements

- Python 3.10+
- Oracle Instant Client (optional, for Oracle connections only)

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

# Execute ad-hoc SQL
dbqm sql "SELECT * FROM table" <connection>

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

Output format options: `--format table|json|csv` and `--export csv|json|txt`.

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
| `↑` `↓` | Navigate items / widgets | Sidebar, lists, tables, forms |
| `←` `→` | Switch folder tabs | Query/group lists |
| `Enter` | Select / Confirm | Global |
| `Escape` | Go back | Global |
| `Ctrl+B` | Toggle sidebar | Global |
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

## Sidebar

| Section | Options |
|---------|---------|
| **Consultas** | Executar, SQL avulso, Gerenciar |
| **Grupos** | Executar, Gerenciar, Templates |
| **Ferramentas** | DDL, Packages, Executar Rotina, Objetos, Historico |
| **Sistema** | Conexoes, Config (inclui Exportar/Importar), Sair |

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
│   ├── ui/
│   │   ├── app.py                 # Main Textual App (layout, routing, keybindings)
│   │   ├── theme.py               # GitHub Dark/Light theme definitions
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
│   │   │   └── config_port.py     # Config export/import (used by settings)
│   │   ├── widgets/               # Reusable UI components
│   │   │   ├── sidebar.py         # Collapsible sidebar with keyboard nav
│   │   │   ├── breadcrumb.py      # Navigation breadcrumb
│   │   │   ├── result_table.py    # DataTable with pagination + vertical view
│   │   │   ├── query_list.py      # Query ListView with search/filter
│   │   │   ├── group_result.py    # Flat/pivoted comparison display
│   │   │   ├── sql_viewer.py      # Syntax-highlighted SQL display
│   │   │   ├── action_bar.py      # Contextual keyboard shortcuts bar
│   │   │   ├── status_bar.py      # Connection status + counters
│   │   │   └── progress.py        # Loading indicator
│   │   ├── modals/                # Dialog screens
│   │   │   ├── param_input.py     # Query parameter input
│   │   │   ├── confirm.py         # Yes/No confirmation
│   │   │   ├── text_input.py      # Single text input
│   │   │   ├── export_picker.py   # Export format selector
│   │   │   ├── connection_form.py # Connection create/edit form
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
│   │   └── audit.py               # Audit logging
│   └── models/                    # Data models (JSON persistence)
│       ├── connection.py          # Connection config
│       ├── query.py               # Query definition
│       ├── group.py               # Query group config
│       └── settings.py            # App settings (theme, audit)
├── config/                        # JSON configs (gitignored)
├── exports/                       # Generated output files (gitignored)
└── tests/                         # Test suite (573+ tests)
    ├── core/                      # Core logic tests
    ├── models/                    # Model tests
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
