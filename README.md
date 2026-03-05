# DB Query Manager (dbqm)

Interactive command-line tool for managing and executing SQL queries across multiple Oracle and SQL Server databases. Built for database maintenance teams that need to compare data across environments, extract DDL, browse database objects, and export results.

## Features

- **Multi-database query execution** — Run saved queries against Oracle (TNS or direct) and SQL Server connections
- **Cross-database comparison** — Execute query groups across databases and compare results side-by-side with match/diff/absent status
- **DDL extraction** — Extract CREATE statements (tables, views, indexes, sequences, packages) with automatic dependency detection
- **Object browser** — Inspect table structure, view definitions, and execute stored procedures with parameter collection
- **Ad-hoc SQL** — Paste and execute SQL with automatic parameter detection and bind variable support
- **Data export** — Export results as CSV, JSON, TXT (formatted tables), PNG (screenshots), HTML reports, and SQL files
- **Encrypted credentials** — Passwords stored with Fernet symmetric encryption
- **Portable configurations** — Export/import connection, query, and group configs as encrypted `.dbqm` bundles
- **Favorites & recent queries** — Star queries and sort by most recently used
- **Paginated results** — Navigate large result sets with next/prev page controls (100 rows per page)
- **In-place query editing** — Edit SQL, params, connection, and table directly from the query wizard
- **Execution history** — Browse the last 100 executions with timing, row counts, and group consistency status
- **HTML comparison reports** — Self-contained HTML files with dark theme, filter buttons, and search
- **Filtered group views** — Show only divergent, absent, or combined rows from group comparisons
- **Audit logging** — Opt-in append-only JSON log of all executions (enable in Settings)
- **Pre-validation** — Validate group bindings (queries, connections, params) before execution
- **Auto-suggest** — Ad-hoc save names and column mappings suggested based on context

## Requirements

- Python 3.x
- Oracle Instant Client (for Oracle connections)

## Installation

```bash
git clone <repo-url>
cd mapfre-sustentacao-py

python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

On first launch, the tool prompts you to configure your first database connection and generates an encryption key (`.dbqm_key`).

### Main Menu

| Option | Description |
|--------|-------------|
| Execute query | Run a saved query with pagination and export |
| Execute group | Run multiple queries across databases and compare results |
| Ad-hoc SQL | Paste and execute SQL directly |
| Extract DDL | Extract DDL from Oracle database objects |
| Object browser | Browse tables, views, and packages |
| Execution history | Browse recent query and group executions |
| Configurations | Manage connections, queries, groups, portability, and settings |

### Query Groups & Comparison

Groups let you run the same logical query across multiple databases and compare results:

- Define a **join key** (row identifier) and **comparison columns**
- Optional **normalization mapping** for semantic equivalence (e.g., "paga" = "pago")
- Optional **column mapping** for when column names differ between queries (auto-suggested by position)
- Results show status per row: `OK`, `DIFF`, `ABSENT`
- Filter results by status (divergent only, absent only, or combined)
- Export as HTML report with interactive filters and search
- Pre-validation checks queries, connections, and parameters before execution
- Summary with match/difference/missing counts

### Parameter Support

Queries support named bind variables (`:param` syntax) with default values and descriptions. Group queries can share parameters — entered once and applied to all queries in the group.

### Column Value Mapping

Transform raw database values into readable labels during display (e.g., status code `1` → `"vencida/pendente"`).

### Execution History

The tool records the last 100 executions (queries and groups) with:
- Timestamp, duration, and row counts
- Group consistency status (CONSISTENTE/DIVERGENTE)
- Parameter values used
- Browsable detail view

### Audit Log

Optional append-only audit log (JSON lines format) that records all executions. Enable via **Configurations > Settings**. Stored at `config/audit.log` with restricted file permissions.

## Project Structure

```
mapfre-sustentacao-py/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── dbqm/                      # Main package
│   ├── ui/                    # User interface
│   │   ├── menu.py            # Main menu system
│   │   ├── flows/             # Feature flows (query, group, DDL, adhoc, history, settings)
│   │   ├── wizards/           # Configuration wizards
│   │   ├── display.py         # Rich-based output formatting
│   │   └── helpers.py         # UI utilities
│   ├── core/                  # Business logic
│   │   ├── db_manager.py      # Database connection handling
│   │   ├── query_engine.py    # SQL execution
│   │   ├── group_engine.py    # Multi-database comparison
│   │   ├── exporter.py        # Export (CSV, JSON, TXT, PNG)
│   │   ├── html_report.py     # Standalone HTML comparison reports
│   │   ├── history.py         # Execution history persistence
│   │   ├── audit.py           # Opt-in audit logging
│   │   ├── ddl_extractor.py   # DDL extraction with dependencies
│   │   ├── object_browser.py  # Database object introspection
│   │   ├── table_browser.py   # Table data browsing
│   │   ├── crypto.py          # Password encryption
│   │   └── config_portability.py  # Config import/export
│   └── models/                # Data models
│       ├── connection.py      # Connection configuration
│       ├── query.py           # Query definition (with favorites)
│       ├── group.py           # Query group configuration
│       └── settings.py        # Application settings
├── config/                    # JSON configs (gitignored)
├── exports/                   # Generated output files (gitignored)
└── tns/                       # Oracle TNS files (gitignored)
```

## Key Dependencies

| Library | Purpose |
|---------|---------|
| `rich` | Terminal UI — tables, panels, spinners, progress bars |
| `InquirerPy` | Interactive menus and prompts |
| `oracledb` | Oracle database driver |
| `pymssql` | SQL Server database driver |
| `cryptography` | Fernet encryption for credentials |
| `sqlparse` | SQL analysis and classification |
| `Pillow` | PNG screenshot export |

## Security

- Database passwords are encrypted at rest using Fernet (`.dbqm_key` master key, `chmod 600`)
- Configuration bundles use PBKDF2 (480,000 iterations) + Fernet for password-protected export
- Queries use bind variables to prevent SQL injection
- SQL identifiers are validated against an allowlist pattern (`[\w#$.]`)
- Query results are capped at 10,000 rows to prevent memory exhaustion
- Config bundle imports are limited to 10 MB
- HTML reports escape all user-controlled values to prevent XSS
- Error messages are truncated to prevent information leakage
- Audit log files are created with restricted permissions (`chmod 600`)
- History files are size-guarded (5 MB limit)
- File open operations are restricted to the exports directory
- Sensitive files are excluded from version control via `.gitignore`
