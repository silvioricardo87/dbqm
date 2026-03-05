# DB Query Manager (dbqm)

Interactive command-line tool for managing and executing SQL queries across multiple Oracle and SQL Server databases. Built for database maintenance teams that need to compare data across environments, extract DDL, browse database objects, and export results.

## Features

- **Multi-database query execution** — Run saved queries against Oracle (TNS or direct) and SQL Server connections
- **Cross-database comparison** — Execute query groups across databases and compare results side-by-side with match/diff/absent status
- **DDL extraction** — Extract CREATE statements (tables, views, indexes, sequences, packages) with automatic dependency detection
- **Object browser** — Inspect table structure, view definitions, and execute stored procedures with parameter collection
- **Ad-hoc SQL** — Paste and execute SQL with automatic parameter detection and bind variable support
- **Data export** — Export results as CSV, JSON, TXT (formatted tables), PNG (screenshots), and SQL files
- **Encrypted credentials** — Passwords stored with Fernet symmetric encryption
- **Portable configurations** — Export/import connection, query, and group configs as encrypted `.dbqm` bundles

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
| Execute query | Run a saved query against a database |
| Execute group | Run multiple queries across databases and compare results |
| Ad-hoc SQL | Paste and execute SQL directly |
| Extract DDL | Extract DDL from Oracle database objects |
| Object browser | Browse tables, views, and packages |
| Configurations | Manage connections, queries, groups, and portability |

### Query Groups & Comparison

Groups let you run the same logical query across multiple databases and compare results:

- Define a **join key** (row identifier) and **comparison columns**
- Optional **normalization mapping** for semantic equivalence (e.g., "paga" = "pago")
- Results show status per row: `✓ OK`, `⚠ DIFF`, `✗ ABSENT`
- Summary with match/difference/missing counts

### Parameter Support

Queries support named bind variables (`:param` syntax) with default values and descriptions. Group queries can share parameters — entered once and applied to all queries in the group.

### Column Value Mapping

Transform raw database values into readable labels during display (e.g., status code `1` → `"vencida/pendente"`).

## Project Structure

```
mapfre-sustentacao-py/
├── main.py                    # Entry point
├── requirements.txt           # Dependencies
├── dbqm/                      # Main package
│   ├── ui/                    # User interface
│   │   ├── menu.py            # Main menu system
│   │   ├── flows/             # Feature flows (query, group, DDL, object browser, adhoc)
│   │   ├── wizards/           # Configuration wizards
│   │   ├── display.py         # Rich-based output formatting
│   │   └── helpers.py         # UI utilities
│   ├── core/                  # Business logic
│   │   ├── db_manager.py      # Database connection handling
│   │   ├── query_engine.py    # SQL execution
│   │   ├── group_engine.py    # Multi-database comparison
│   │   ├── exporter.py        # Export (CSV, JSON, TXT, PNG)
│   │   ├── ddl_extractor.py   # DDL extraction with dependencies
│   │   ├── object_browser.py  # Database object introspection
│   │   ├── table_browser.py   # Table data browsing
│   │   ├── crypto.py          # Password encryption
│   │   └── config_portability.py  # Config import/export
│   └── models/                # Data models
│       ├── connection.py      # Connection configuration
│       ├── query.py           # Query definition
│       └── group.py           # Query group configuration
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

- Database passwords are encrypted at rest using Fernet (`.dbqm_key` master key)
- Configuration bundles use PBKDF2 + Fernet for password-protected export
- Queries use bind variables to prevent SQL injection
- Sensitive files are excluded from version control via `.gitignore`
